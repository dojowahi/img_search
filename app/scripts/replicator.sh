#!/bin/bash

# Check if the correct number of arguments is provided
if [ $# -ne 3 ]; then
  echo "Usage: $0 <app_dir> <company> <abbv>"
  exit 1
fi

app_dir="$1"
comp_name="$2"
comp_abbv="$3"

source_folder="${app_dir}/templates/prototype/"
destination_folder="${app_dir}/templates/${comp_abbv}"

echo "Source:${source_folder}"
echo "Destination:${destination_folder}"
# Check if the source folder exists
if [ ! -d "$source_folder" ]; then
  echo "Error: Source folder '$source_folder' not found."
  exit 1
fi

# Create the destination folder if it doesn't exist
mkdir -p "$destination_folder"

if [ ! -d "$destination_folder" ]; then
  echo "Error: Destination folder '$destination_folder' not found."
  exit 1
fi

# Copy the source folder to the destination folder
cp -r ${source_folder}/* ${destination_folder}/

if [ -f "$destination_folder/index.html" ]; then
  sed -i "s/comp_name/${comp_name}/g" "$destination_folder/index.html"
  sed -i "s/comp_abbv/${comp_abbv}/g" "$destination_folder/index.html"
else
  echo "Warning: index.html not found in destination folder."
fi

# Append Python code to main.py
python_code='
@app.get("/'"${comp_abbv}"'", response_class=HTMLResponse)
async def '"${comp_abbv}"'(request: Request):
    """'"${comp_name}"'-branded frontend"""
    return templates.TemplateResponse(
        "'"${comp_abbv}"'/index.html",
        {"request": request, "brand": "'"${abbv}"'", "brand_config": BRAND_CONFIG["'"${comp_abbv}"'"]}
    )

'

if [[ ${app_dir} == /app/app* ]]; then
  echo "$python_code" >> /app/main.py
else
  echo "$python_code" >> ${app_dir}/main.py
fi

# # Check if the copy was successful
if [ $? -eq 0 ]; then
  echo "Folder '$source_folder' copied to '$destination_folder' successfully."
else
  echo "Error: Failed to copy folder '$source_folder' to '$destination_folder'."
  exit 1
fi

exit 0