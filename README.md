
# NRRD to STL Converter

**NRRD to STL Converter** is a GUI-based Python application designed to convert `.nrrd` medical image files into 3D surface models saved in the `.stl` format. The application allows users to set custom parameters, apply mesh optimization techniques, and visually monitor the conversion process. It is built using `PyQt5` for the graphical interface, `SimpleITK` for image processing, and `VTK` for 3D model manipulation and file conversion.

## Key Features

- **Graphical User Interface (GUI)**: Easy-to-use interface built with `PyQt5` for selecting and converting `.nrrd` files to `.stl`.
- **Binary Thresholding and Morphological Operations**: Allows users to set a threshold value to segment the 3D volume and apply morphological operations like closing to refine the mesh.
- **Mesh Optimization**: Includes options to decimate (reduce the number of triangles) and smooth the mesh, preserving topology and ensuring a clean surface.
- **Estimation and Feedback**: Provides real-time feedback on the estimated output size and triangle count, allowing users to adjust settings accordingly.
- **Threaded Execution**: Multi-threaded processing ensures that the GUI remains responsive during the conversion process.

## How It Works

1. **Load NRRD File**: Select the `.nrrd` file you want to convert.
2. **Set Threshold Value**: Adjust the threshold value to extract the desired region of interest from the medical image.
3. **Decimate and Optimize**: Enable the decimation option to reduce the triangle count and set the reduction factor as needed.
4. **Convert and Save**: Click on `Convert to STL` to start the conversion. The final `.stl` file can be saved to your desired location.
5. **View Progress and Results**: The application displays progress updates and estimated output sizes based on the chosen settings.

## Dependencies

The following Python libraries are required to run this script:

- `SimpleITK`: Used for image processing and manipulation of NRRD files.
- `VTK` (Visualization Toolkit): Handles 3D mesh generation and export to STL format.
- `PyQt5`: Provides the graphical user interface components.
- `numpy`: Supports array manipulation and operations.

To install the necessary dependencies, run:

```bash
pip install SimpleITK vtk PyQt5 numpy
```

## How to Use

1. **Run the Script**:
   ```bash
   python nrrd_to_stl_converter.py
   ```
2. **Select a NRRD File**: Use the `Select NRRD File` button to choose the `.nrrd` file you want to process.
3. **Set Parameters**:
   - Adjust the threshold value to control which parts of the 3D image are extracted.
   - Enable or disable the decimation option and set the reduction percentage if needed.
4. **Convert to STL**: Click the `Convert to STL` button to start the conversion process.
5. **Save the STL File**: After conversion, save the `.stl` file to your desired location.

## License

This software is licensed under the MIT License. See the `LICENSE` file for more details.

## Acknowledgements

This tool leverages the power of `SimpleITK`, `VTK`, and `PyQt5` to provide an efficient and user-friendly conversion experience. Special thanks to the contributors and maintainers of these libraries for their work.

## Limitations

- This script currently supports only `.nrrd` files as input.
- Depending on the size of the input file and the chosen parameters, the conversion process might take considerable time and memory.
