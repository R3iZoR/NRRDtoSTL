import sys
import os
import SimpleITK as sitk
import vtk
from vtk.util import numpy_support
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLabel, QLineEdit, QPushButton,
    QFileDialog, QVBoxLayout, QWidget, QHBoxLayout, QSlider, QCheckBox,
    QProgressBar
)
from PyQt5.QtCore import Qt, QThreadPool, QRunnable, pyqtSignal, QObject

class WorkerSignals(QObject):
    estimation_done = pyqtSignal(float)
    triangles_info = pyqtSignal(int, int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

class EstimationWorker(QRunnable):
    def __init__(self, nrrd_file, threshold_value, decimate_enabled, decimate_value):
        super().__init__()
        self.nrrd_file = nrrd_file
        self.threshold_value = threshold_value
        self.decimate_enabled = decimate_enabled
        self.decimate_value = decimate_value
        self.signals = WorkerSignals()

    def run(self):
        try:
            # Set the number of threads for SimpleITK
            sitk.ProcessObject_SetGlobalDefaultNumberOfThreads(os.cpu_count())

            # Load image
            itk_image = sitk.ReadImage(self.nrrd_file)
            spacing = itk_image.GetSpacing()
            origin = itk_image.GetOrigin()

            # Apply binary threshold
            thresholded_image = sitk.BinaryThreshold(
                itk_image,
                lowerThreshold=self.threshold_value,
                upperThreshold=1e6,
                insideValue=1,
                outsideValue=0
            )

            # Apply morphological closing
            radius = (1, 1, 1)  # Adjust radius as needed
            closed_image = sitk.BinaryMorphologicalClosing(thresholded_image, radius)

            # Convert to numpy array
            np_image = sitk.GetArrayFromImage(closed_image)

            # Correct data orientation
            np_image = np.transpose(np_image, (2, 1, 0))  # From (z, y, x) to (x, y, z)

            vtk_image = vtk.vtkImageData()
            vtk_image.SetDimensions(np_image.shape)
            vtk_image.SetSpacing(spacing)
            vtk_image.SetOrigin(origin)

            flat_data_array = np_image.ravel(order='F')
            vtk_np_image = numpy_support.numpy_to_vtk(
                num_array=flat_data_array,
                deep=True,
                array_type=vtk.VTK_UNSIGNED_CHAR
            )
            vtk_image.GetPointData().SetScalars(vtk_np_image)

            # Apply Flying Edges (multithreaded isosurface extraction)
            contour = vtk.vtkFlyingEdges3D()
            contour.SetInputData(vtk_image)
            contour.SetValue(0, 0.5)
            contour.ComputeNormalsOff()
            contour.Update()

            polydata = contour.GetOutput()
            num_triangles_before = polydata.GetNumberOfPolys()

            # Apply connectivity filter to extract the largest region
            connectivity_filter = vtk.vtkPolyDataConnectivityFilter()
            connectivity_filter.SetInputData(polydata)
            connectivity_filter.SetExtractionModeToLargestRegion()
            connectivity_filter.Update()
            polydata = connectivity_filter.GetOutput()

            # Fill holes to ensure watertight mesh
            fill_holes_filter = vtk.vtkFillHolesFilter()
            fill_holes_filter.SetInputData(polydata)
            fill_holes_filter.SetHoleSize(1000.0)  # Adjust as needed
            fill_holes_filter.Update()
            polydata = fill_holes_filter.GetOutput()

            # Clean the mesh to remove any duplicate points or unused data
            cleaner = vtk.vtkCleanPolyData()
            cleaner.SetInputData(polydata)
            cleaner.Update()
            polydata = cleaner.GetOutput()

            # Ensure the mesh has triangles
            triangle_filter = vtk.vtkTriangleFilter()
            triangle_filter.SetInputData(polydata)
            triangle_filter.Update()
            polydata = triangle_filter.GetOutput()

            # Recompute normals to ensure consistency
            normals = vtk.vtkPolyDataNormals()
            normals.SetInputData(polydata)
            normals.ConsistencyOn()
            normals.SplittingOff()
            normals.AutoOrientNormalsOn()
            normals.ComputePointNormalsOn()
            normals.ComputeCellNormalsOn()
            normals.Update()
            polydata = normals.GetOutput()

            num_triangles_before = polydata.GetNumberOfPolys()

            # Decimate if enabled
            if self.decimate_enabled:
                reduction = self.decimate_value / 100.0
                decimate = vtk.vtkDecimatePro()
                decimate.SetInputData(polydata)
                decimate.SetTargetReduction(reduction)
                decimate.PreserveTopologyOn()  # Preserve topology to maintain perimeters
                decimate.SplittingOff()
                decimate.BoundaryVertexDeletionOff()
                decimate.Update()
                polydata = decimate.GetOutput()
                num_triangles_after = polydata.GetNumberOfPolys()
            else:
                num_triangles_after = num_triangles_before

            # Emit triangle counts for display
            self.signals.triangles_info.emit(num_triangles_before, num_triangles_after)

            # Estimate size based on triangle count
            estimated_size = num_triangles_after * 50  # Approximate bytes per triangle
            estimated_size_mb = estimated_size / (1024 * 1024)

            # Emit signal with the estimated size
            self.signals.estimation_done.emit(estimated_size_mb)
        except Exception as e:
            # Emit -1 to indicate an error
            self.signals.estimation_done.emit(-1)
            self.signals.error.emit(str(e))

class ConversionWorker(QRunnable):
    def __init__(self, nrrd_file, threshold_value, decimate_enabled, decimate_value, output_file):
        super().__init__()
        self.nrrd_file = nrrd_file
        self.threshold_value = threshold_value
        self.decimate_enabled = decimate_enabled
        self.decimate_value = decimate_value
        self.output_file = output_file
        self.signals = WorkerSignals()

    def run(self):
        try:
            # Set the number of threads for SimpleITK
            sitk.ProcessObject_SetGlobalDefaultNumberOfThreads(os.cpu_count())

            # Read the NRRD file
            itk_image = sitk.ReadImage(self.nrrd_file)
            spacing = itk_image.GetSpacing()
            origin = itk_image.GetOrigin()

            # Apply binary threshold
            thresholded_image = sitk.BinaryThreshold(
                itk_image,
                lowerThreshold=self.threshold_value,
                upperThreshold=1e6,
                insideValue=1,
                outsideValue=0
            )

            # Apply morphological closing
            radius = (1, 1, 1)  # Adjust radius as needed
            closed_image = sitk.BinaryMorphologicalClosing(thresholded_image, radius)

            # Convert to numpy array
            np_image = sitk.GetArrayFromImage(closed_image)

            # Correct data orientation
            np_image = np.transpose(np_image, (2, 1, 0))  # From (z, y, x) to (x, y, z)

            vtk_image = vtk.vtkImageData()
            vtk_image.SetDimensions(np_image.shape)
            vtk_image.SetSpacing(spacing)
            vtk_image.SetOrigin(origin)

            flat_data_array = np_image.ravel(order='F')
            vtk_np_image = numpy_support.numpy_to_vtk(
                num_array=flat_data_array,
                deep=True,
                array_type=vtk.VTK_UNSIGNED_CHAR
            )
            vtk_image.GetPointData().SetScalars(vtk_np_image)

            # Apply Flying Edges (multithreaded isosurface extraction)
            contour = vtk.vtkFlyingEdges3D()
            contour.SetInputData(vtk_image)
            contour.SetValue(0, 0.5)
            contour.ComputeNormalsOff()
            contour.Update()

            polydata = contour.GetOutput()

            # Apply connectivity filter to extract the largest region
            connectivity_filter = vtk.vtkPolyDataConnectivityFilter()
            connectivity_filter.SetInputData(polydata)
            connectivity_filter.SetExtractionModeToLargestRegion()
            connectivity_filter.Update()
            polydata = connectivity_filter.GetOutput()

            # Fill holes to ensure watertight mesh
            fill_holes_filter = vtk.vtkFillHolesFilter()
            fill_holes_filter.SetInputData(polydata)
            fill_holes_filter.SetHoleSize(1000.0)  # Adjust as needed
            fill_holes_filter.Update()
            polydata = fill_holes_filter.GetOutput()

            # Clean the mesh to remove any duplicate points or unused data
            cleaner = vtk.vtkCleanPolyData()
            cleaner.SetInputData(polydata)
            cleaner.Update()
            polydata = cleaner.GetOutput()

            # Ensure the mesh has triangles
            triangle_filter = vtk.vtkTriangleFilter()
            triangle_filter.SetInputData(polydata)
            triangle_filter.Update()
            polydata = triangle_filter.GetOutput()

            # Optionally smooth the mesh to reduce noise
            smoother = vtk.vtkWindowedSincPolyDataFilter()
            smoother.SetInputData(polydata)
            smoother.SetNumberOfIterations(15)
            smoother.BoundarySmoothingOff()
            smoother.FeatureEdgeSmoothingOff()
            smoother.SetFeatureAngle(120.0)
            smoother.SetPassBand(0.001)
            smoother.NonManifoldSmoothingOn()
            smoother.NormalizeCoordinatesOn()
            smoother.Update()
            polydata = smoother.GetOutput()

            # Recompute normals to ensure consistency
            normals = vtk.vtkPolyDataNormals()
            normals.SetInputData(polydata)
            normals.ConsistencyOn()
            normals.SplittingOff()
            normals.AutoOrientNormalsOn()
            normals.ComputePointNormalsOn()
            normals.ComputeCellNormalsOn()
            normals.Update()
            polydata = normals.GetOutput()

            num_triangles_before = polydata.GetNumberOfPolys()

            # Decimate if enabled
            if self.decimate_enabled:
                reduction = self.decimate_value / 100.0
                decimate = vtk.vtkDecimatePro()
                decimate.SetInputData(polydata)
                decimate.SetTargetReduction(reduction)
                decimate.PreserveTopologyOn()  # Preserve topology to maintain perimeters
                decimate.SplittingOff()
                decimate.BoundaryVertexDeletionOff()
                decimate.Update()
                polydata = decimate.GetOutput()
                num_triangles_after = polydata.GetNumberOfPolys()
            else:
                num_triangles_after = num_triangles_before

            # Optionally, you can log the triangle counts
            print(f"Triangles before decimation: {num_triangles_before}")
            print(f"Triangles after decimation: {num_triangles_after}")

            # Save as STL
            stl_writer = vtk.vtkSTLWriter()
            stl_writer.SetFileName(self.output_file)
            stl_writer.SetInputData(polydata)
            stl_writer.SetFileTypeToBinary()  # Use binary for smaller file size
            stl_writer.Write()

            # Emit finished signal
            self.signals.finished.emit(self.output_file)
        except Exception as e:
            self.signals.error.emit(str(e))

class NRRDToSTLConverter(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('NRRD to STL Converter')

        # Initialize variables
        self.nrrd_file = None
        self.decimate_enabled = True
        self.estimation_running = False

        self.initUI()
        self.threadpool = QThreadPool()

    def initUI(self):
        # Widgets
        self.file_label = QLabel('No file selected')
        self.select_button = QPushButton('Select NRRD File')
        self.select_button.clicked.connect(self.select_file)

        self.threshold_label = QLabel('Threshold Value:')
        self.threshold_input = QLineEdit('500')
        self.threshold_input.editingFinished.connect(self.update_estimate)

        self.decimate_checkbox = QCheckBox('Decimate Mesh')
        self.decimate_checkbox.stateChanged.connect(self.toggle_decimate)
        self.decimate_checkbox.setChecked(True)

        self.decimate_label = QLabel('Reduction Factor:')
        self.decimate_slider = QSlider(Qt.Horizontal)
        self.decimate_slider.setMinimum(1)
        self.decimate_slider.setMaximum(99)
        self.decimate_slider.setValue(50)
        self.decimate_slider.setTickPosition(QSlider.TicksBelow)
        self.decimate_slider.setTickInterval(10)
        self.decimate_value_label = QLabel('50%')

        self.decimate_slider.valueChanged.connect(self.update_decimate_value_label)
        self.decimate_slider.sliderReleased.connect(self.update_estimate)

        self.estimate_label = QLabel('Estimated Output Size: N/A')
        self.triangle_counts_label = QLabel('Triangles: N/A')  # New label for triangle counts

        self.convert_button = QPushButton('Convert to STL')
        self.convert_button.clicked.connect(self.convert_to_stl)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate progress bar
        self.progress_bar.hide()

        # Layouts
        layout = QVBoxLayout()
        layout.addWidget(self.file_label)
        layout.addWidget(self.select_button)

        threshold_layout = QHBoxLayout()
        threshold_layout.addWidget(self.threshold_label)
        threshold_layout.addWidget(self.threshold_input)
        layout.addLayout(threshold_layout)

        layout.addWidget(self.decimate_checkbox)

        decimate_layout = QHBoxLayout()
        decimate_layout.addWidget(self.decimate_label)
        decimate_layout.addWidget(self.decimate_slider)
        decimate_layout.addWidget(self.decimate_value_label)
        layout.addLayout(decimate_layout)

        layout.addWidget(self.estimate_label)
        layout.addWidget(self.triangle_counts_label)  # Add triangle counts label
        layout.addWidget(self.convert_button)
        layout.addWidget(self.progress_bar)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def select_file(self):
        options = QFileDialog.Options()
        fileName, _ = QFileDialog.getOpenFileName(
            self, "Select NRRD File", "",
            "NRRD Files (*.nrrd);;All Files (*)", options=options
        )
        if fileName:
            self.nrrd_file = fileName
            self.file_label.setText(os.path.basename(fileName))
            self.update_estimate()

    def toggle_decimate(self, state):
        self.decimate_enabled = (state == Qt.Checked)
        self.update_estimate()

    def update_decimate_value_label(self, value):
        self.decimate_value_label.setText(f'{value}%')
        # Do not update estimate here; wait until slider is released

    def update_estimate(self):
        if self.estimation_running:
            return  # Prevent multiple estimations running simultaneously
        if self.nrrd_file:
            self.estimation_running = True
            try:
                threshold_value = float(self.threshold_input.text())
            except ValueError:
                threshold_value = 0

            decimate_value = self.decimate_slider.value()

            # Start estimation in a separate thread using QThreadPool
            estimation_worker = EstimationWorker(
                self.nrrd_file, threshold_value, self.decimate_enabled, decimate_value
            )
            estimation_worker.signals.estimation_done.connect(self.on_estimation_done)
            estimation_worker.signals.triangles_info.connect(self.update_triangle_counts)
            estimation_worker.signals.error.connect(self.on_estimation_error)
            self.threadpool.start(estimation_worker)

    def update_triangle_counts(self, before, after):
        self.triangle_counts_label.setText(f'Triangles: Before Decimation: {before}, After Decimation: {after}')

    def on_estimation_done(self, estimated_size_mb):
        if estimated_size_mb >= 0:
            self.estimate_label.setText(f'Estimated Output Size: {estimated_size_mb:.2f} MB')
        else:
            self.estimate_label.setText('Estimated Output Size: Error during estimation.')
        self.estimation_running = False

    def on_estimation_error(self, error_message):
        self.estimate_label.setText('Estimated Output Size: Error during estimation.')
        self.triangle_counts_label.setText(f'Triangles: Error - {error_message}')
        self.estimation_running = False

    def convert_to_stl(self):
        if not self.nrrd_file:
            self.file_label.setText('Please select a file first!')
            return

        options = QFileDialog.Options()
        fileName, _ = QFileDialog.getSaveFileName(
            self, "Save STL File", "",
            "STL Files (*.stl);;All Files (*)", options=options
        )
        if fileName:
            try:
                threshold_value = float(self.threshold_input.text())
            except ValueError:
                threshold_value = 0

            decimate_value = self.decimate_slider.value()

            # Disable UI elements during processing
            self.convert_button.setEnabled(False)
            self.select_button.setEnabled(False)
            self.progress_bar.show()

            # Start conversion in a separate thread using QThreadPool
            conversion_worker = ConversionWorker(
                self.nrrd_file, threshold_value, self.decimate_enabled, decimate_value, fileName
            )
            conversion_worker.signals.finished.connect(self.on_conversion_finished)
            conversion_worker.signals.error.connect(self.on_conversion_error)
            self.threadpool.start(conversion_worker)

    def on_conversion_finished(self, output_file):
        self.file_label.setText(f'File saved: {os.path.basename(output_file)}')
        # Re-enable UI elements
        self.convert_button.setEnabled(True)
        self.select_button.setEnabled(True)
        self.progress_bar.hide()

    def on_conversion_error(self, error_message):
        self.file_label.setText(f'Error: {error_message}')
        # Re-enable UI elements
        self.convert_button.setEnabled(True)
        self.select_button.setEnabled(True)
        self.progress_bar.hide()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    converter = NRRDToSTLConverter()
    converter.show()
    sys.exit(app.exec_())
