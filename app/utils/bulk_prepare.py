# simple_bulk.py
import argparse
import json
import os


def create_simple_bulk_file(image_dir, output_file):
    """Create a simple bulk upload JSON file"""
    # Get image files
    image_files = []
    for file in os.listdir(image_dir):
        if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
            image_files.append(os.path.join(image_dir, file))
    
    print(f"Found {len(image_files)} images")
    
    # Create simple structure
    data = []
    for path in image_files:
        item = {
            "id": os.path.basename(path).split('.')[0],
            "image_path": os.path.abspath(path),
            "metadata": {
                "source": "simple_bulk"
            }
        }
        data.append(item)
    
    # Write to file
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"Created {output_file} with {len(data)} items")
    print(f"Try: curl -X POST -F 'file=@{output_file}' http://localhost:8000/api/v1/bulk_upload/")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("image_dir", help="Directory with images")
    parser.add_argument("-o", "--output", default="simple_bulk.json", help="Output JSON file")
    args = parser.parse_args()
    
    create_simple_bulk_file(args.image_dir, args.output)