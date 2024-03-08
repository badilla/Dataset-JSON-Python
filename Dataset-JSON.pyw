
import os
import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox
import pandas as pd
import pyreadstat
import saxonche
import datetime
import time
import json
import jsonschema

# Global Variable Path
path = os.path.abspath(".")

# Datetime to Integer Function
def datetime_to_integer(dt):
    if isinstance(dt, datetime.date):
        # For date objects, convert to SAS date representation
        days_since_epoch = (dt - datetime.date(1960, 1, 1)).days
        return days_since_epoch
    elif isinstance(dt, datetime.datetime):
        # For datetime objects, convert to SAS date representation
        days_since_epoch = (dt.date() - datetime.date(1960, 1, 1)).days
        seconds_since_midnight = (dt.hour * 3600 + dt.minute * 60 + dt.second + dt.microsecond / 1e6)
        return days_since_epoch + seconds_since_midnight / 86400
    elif isinstance(dt, datetime.time):
        # For time objects, convert to SAS date representation (time-only)
        seconds_since_midnight = (dt.hour * 3600 + dt.minute * 60 + dt.second + dt.microsecond / 1e6)
        return seconds_since_midnight / 86400
    
# Main Function
def main():

    # Create window
    window = tk.Tk()
    window.title("Dataset-JSON Creation (Beta Version 0.01)")

    # Define.xml input field
    define_label = tk.Label(window, text="Define.xml", width=17)
    define_label.grid(row=0, column=0)
    define_var = tk.StringVar()
    define_entry = tk.Entry(window, textvariable=define_var, width=65, state="readonly")
    define_entry.grid(row=0, column=1)
    define_button = tk.Button(window, text="Browse", command=lambda: browse_file(define_var))
    define_button.grid(row=0, column=2)

    # SAS Datasets Library input field
    library_label = tk.Label(window, text="SAS Datasets Library", width=17)
    library_label.grid(row=1, column=0)
    library_var = tk.StringVar()
    library_entry = tk.Entry(window, textvariable=library_var, width=65, state="readonly")
    library_entry.grid(row=1, column=1)
    library_button = tk.Button(window, text="Browse", command=lambda: browse_directory(library_var))
    library_button.grid(row=1, column=2)

    # Dataset-JSON Folder input field
    folder_label = tk.Label(window, text="Dataset-JSON Folder", width=17)
    folder_label.grid(row=2, column=0)
    folder_var = tk.StringVar()
    folder_entry = tk.Entry(window, textvariable=folder_var, width=65, state="readonly")
    folder_entry.grid(row=2, column=1)
    folder_button = tk.Button(window, text="Browse", command=lambda: browse_directory(folder_var))
    folder_button.grid(row=2, column=2)

    # Radio buttons for selecting file type
    file_type_frame = tk.Frame(window)
    file_type_frame.grid(row=3, column=0, columnspan=3)
    sas_var = tk.BooleanVar(value=True)
    sas_radio = tk.Radiobutton(file_type_frame, text="SAS7BDAT", variable=sas_var, value=True)
    sas_radio.pack(side="left")
    xpt_radio = tk.Radiobutton(file_type_frame, text="XPT", variable=sas_var, value=False)
    xpt_radio.pack(side="left")
    sas_radio.select()

    # Submit and Cancel buttons
    submit_button = tk.Button(window, text="Submit", command=lambda: process_files(define_var.get(), library_var.get(), folder_var.get(), sas_var.get(), not sas_var.get()))
    submit_button.grid(row=4, column=0)
    cancel_button = tk.Button(window, text="Cancel", command=window.quit)
    cancel_button.grid(row=4, column=1)

    window.mainloop()

# Function to browse and select a file
def browse_file(entry_var):
    file_path = filedialog.askopenfilename(filetypes=(("XML Files", "*.xml"),))
    entry_var.set(file_path)

# Function to browse and select a directory
def browse_directory(entry_var):
    directory_path = filedialog.askdirectory()
    entry_var.set(directory_path)

# Function to process the files and create Dataset-JSON files
def process_files(define_path, library_path, folder_path, is_sas, is_xpt):
    define = define_path
    library = library_path
    folder = folder_path
    sas = is_sas
    xpt = is_xpt

    # Popup error window when required fields are not filled out
    if any((define == "", library == "", folder == "")):
        messagebox.showerror("", "Please fill out required fields")
        return

    # Check if Dataset-JSON stylesheet exists where it should. 
    if not (os.path.isfile(os.path.join(path, "Stylesheet", "Dataset-JSON.xsl"))):
        messagebox.showerror("", "Stylesheet Dataset-JSON.xsl file not found. Make sure it is located in a subfolder Stylesheet.")
        return

    # Check if Dataset-JSON schema exists where it should. 
    if not (os.path.isfile(os.path.join(path, "Schema", "dataset.schema.json"))):
        messagebox.showerror("", "Schema dataset.schema.json file not found. Make sure it is located in a subfolder Schema.")
        return

    # Create Dataset-JSON files    
    files = [file for file in os.listdir(library) if file.endswith(".sas7bdat")] if sas else [file for file in os.listdir(library) if file.endswith(".xpt")] if xpt else []

    if files:
        messagebox.showinfo("", "Processing....")
        
        for file in files:

            # Extract data and metadata from either SAS or XPT datasets
            if sas:
                df, meta = pyreadstat.read_sas7bdat(os.path.join(library, file))
            elif xpt:
                df, meta = pyreadstat.read_xport(os.path.join(library, file))

            dsname = file.upper().rsplit('.', 1)[0]

            # Extract Dataset-JSON metadata from Define.xml
            processor = saxonche.PySaxonProcessor(license=False)
            xslt = processor.new_xslt30_processor()
            xslt.set_parameter("dsName", processor.make_string_value(dsname))
            xslt.set_parameter("creationDateTime", processor.make_string_value(datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")))
            xslt.set_parameter("nbRows", processor.make_integer_value(meta.number_rows))
            result = xslt.transform_to_string(source_file=define, stylesheet_file=os.path.join(path, "Stylesheet", "Dataset-JSON.xsl"))
            json_data = json.loads(result)

            if "clinicalData" in json_data:
                data_key = "clinicalData"
            elif "referenceData" in json_data:
                data_key = "referenceData"

            items = json_data[data_key]["itemGroupData"][dsname]["items"]

            pairs = {item["name"]: item["type"] for item in items if item["name"] != "ITEMGROUPDATASEQ"}

            if sorted([col.upper() for col in df.columns.tolist()]) == sorted([item["name"].upper() for item in items if item["name"] != "ITEMGROUPDATASEQ"]):

                # Extract Dataset-JSON data from each SAS or XPT datasets
                records = ''
                if meta.number_rows > 0:
                    for index, row in df.iterrows():
                        if index > 0:
                            records += ','
                        records += '[' + str(index + 1)
                        for column in df.columns:
                            type = pairs[column]
                            value = row[column]
                            records += ','
                            if isinstance(value, (datetime.date, datetime.datetime, datetime.time)):
                                records += str(datetime_to_integer(value))
                            elif type == "string":
                                records += json.dumps(value) 
                            elif type == "integer":
                                if pd.isna(value):
                                    records += "null"
                                elif value == "":
                                    records += "null"
                                else:
                                    records += json.dumps(int(value))
                            else:
                                if pd.isna(value):
                                    records += "null"
                                else:
                                    records += json.dumps(value) 
                        records += ']'

                json_data[data_key]["itemGroupData"][dsname]["itemData"] = json.loads("[" + records + "]")

                # Load Dataset-JSON Schema
                with open(os.path.join(path, "Schema", "dataset.schema.json")) as schemajson:
                    schema = schemajson.read()
                schema = json.loads(schema)

                # Check if JSON file is valid against the Dataset-JSON schema
                error = False
                try:
                    jsonschema.validate(json_data, schema)
                except:
                    error = True

                # Save Dataset-JSON files
                if not error:
                    try:
                        with open(os.path.join(folder, dsname) + ".json", "w") as json_file:
                            json.dump(json_data, json_file)
                    except:
                        error = True

                # Add the SAS or XPT files that are not compliant with either JSON or Dataset-JSON schema
                if error:
                    messagebox.showwarning("", f"The file {file} is not compliant with either JSON or Dataset-JSON schema")

            else:
                messagebox.showwarning("", f"The file {file} is not compliant with either JSON or Dataset-JSON schema")

        # Pop-up when all files are compliant with Dataset-JSON standard
        messagebox.showinfo("", "Dataset-JSON files created.")

    else:
        messagebox.showwarning("", "No datasets found in the selected directory. Please check.")

if __name__ == '__main__':
    main()
