# PyHexCominator

PyHexCominator combines two Intel HEX files into one `Combined.hex` file.

The bootloader file is written first, then the main application file. The input EOF records are removed and one final EOF record is added to the combined file.

## Command line

```powershell
python hex_combine.py C:\path\Bootloader.hex C:\path\MainApp.hex
```

By default, `Combined.hex` is created in the bootloader file's folder.

To choose a different output path:

```powershell
python hex_combine.py C:\path\Bootloader.hex C:\path\MainApp.hex -o C:\path\Combined.hex
```

## GUI

Install the optional drag-and-drop dependency:

```powershell
pip install -r requirements.txt
```

Run the GUI:

```powershell
python hex_combine_gui.py
```

Drop the bootloader HEX file into the Bootloader box, drop the main application HEX file into the MainApp box, then select `Combine`.

If `tkinterdnd2` is not installed, the GUI still works by typing paths or using the Browse buttons.
