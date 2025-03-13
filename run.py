import os

import uvicorn

print(f"Current working directory: {os.getcwd()}")
print(f"Static directory exists: {os.path.exists('./app/static')}")
print(f"Listing directory contents: {os.listdir('.')}")

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)