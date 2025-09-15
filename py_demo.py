import sys
import ctypes
import numpy as np
import cv2
import os

# 定义MatchResult结构体
class MatchResult(ctypes.Structure):
    _fields_ = [
        ('leftTopX', ctypes.c_double),
        ('leftTopY', ctypes.c_double),
        ('leftBottomX', ctypes.c_double),
        ('leftBottomY', ctypes.c_double),
        ('rightTopX', ctypes.c_double),
        ('rightTopY', ctypes.c_double),
        ('rightBottomX', ctypes.c_double),
        ('rightBottomY', ctypes.c_double),
        ('centerX', ctypes.c_double),
        ('centerY', ctypes.c_double),
        ('angle', ctypes.c_double),
        ('score', ctypes.c_double)
    ]

# 定义Matcher类
class Matcher:
    def __init__(self, dll_path, maxCount, scoreThreshold, iouThreshold, angle, minArea):
        # Load the library
        try:
            self.lib = ctypes.CDLL(dll_path)
            print(f"Successfully loaded library: {dll_path}")
        except OSError as e:
            print(f"Failed to load library {dll_path}: {e}")
            raise

        # Define function signatures
        self.lib.matcher.argtypes = [ctypes.c_int, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float]
        self.lib.matcher.restype = ctypes.c_void_p
        self.lib.setTemplate.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ubyte), ctypes.c_int, ctypes.c_int, ctypes.c_int]
        self.lib.setTemplate.restype = ctypes.c_int
        self.lib.match.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ubyte), ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.POINTER(MatchResult), ctypes.c_int]
        self.lib.match.restype = ctypes.c_int
        
        if maxCount <= 0:
            raise ValueError("maxCount must be greater than 0")
        self.maxCount = maxCount
        self.scoreThreshold = scoreThreshold
        self.iouThreshold = iouThreshold
        self.angle = angle
        self.minArea = minArea
        
        # Create matcher
        self.matcher = self.lib.matcher(maxCount, scoreThreshold, iouThreshold, angle, minArea)
        if not self.matcher:
            raise RuntimeError("Failed to create matcher")

        self.results = (MatchResult * self.maxCount)()
    
    def set_template(self, image):
        height, width = image.shape[0], image.shape[1]
        channels = 1
        data = image.ctypes.data_as(ctypes.POINTER(ctypes.c_ubyte))
        result = self.lib.setTemplate(self.matcher, data, width, height, channels)
        return result
    
    def match(self, image):
        # Convert to grayscale if needed
        if image.ndim == 3:
            if image.shape[2] == 3:
                image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            elif image.shape[2] == 1:
                image = image[:, :, 0]
            else:
                raise ValueError("Invalid image shape")
        elif image.ndim != 2:
            raise ValueError("Invalid image shape")
            
        height, width = image.shape[0], image.shape[1]
        channels = 1
        data = image.ctypes.data_as(ctypes.POINTER(ctypes.c_ubyte))
        result = self.lib.match(self.matcher, data, width, height, channels, self.results, self.maxCount)
        return result

    def __del__(self):
        # In a more complete implementation, we would clean up the matcher here
        pass

# 示例调用
maxCount = 10
scoreThreshold = 0.5
iouThreshold = 0.4
angle = 0
minArea = 256

# Use the correct library path for the current platform
if sys.platform == "darwin":  # macOS
    dll_path = './libtemplatematching_ctype.dylib'
elif sys.platform == "win32":  # Windows
    dll_path = './templatematching_ctype.dll'
else:  # Linux and others
    dll_path = './libtemplatematching_ctype.so'

# Check if library exists
if not os.path.exists(dll_path):
    print(f"Library not found: {dll_path}")
    print("Please copy the library to the current directory or update the path")
    sys.exit(1)

try:
    # 创建Matcher对象
    print("Creating Matcher object...")
    matcher = Matcher(dll_path, maxCount, scoreThreshold, iouThreshold, angle, minArea)
    print("Matcher created successfully")
except Exception as e:
    print(f"Failed to create Matcher: {e}")
    sys.exit(1)

# 读取模板图像
image = cv2.imread('image.png', cv2.IMREAD_GRAYSCALE)
if image is None:
    print("Template image not found. Creating a simple test image...")
    # Create a simple test template
    image = np.ones((100, 100), dtype=np.uint8) * 255
    cv2.rectangle(image, (20, 20), (80, 80), (0, 0, 0), -1)
    cv2.imwrite('test_template.png', image)
    print("Created test_template.png")

# 设置模板
print("Setting template...")
result = matcher.set_template(image)
if result != 0:
    print(f"Failed to set template, error code: {result}")
    sys.exit(1)
print("Template set successfully")

# For demo purposes, we'll create a simple target image and match against it
# instead of using a camera
print("Creating test target image...")
target = np.ones((400, 400), dtype=np.uint8) * 255
# Add the same pattern at different locations
cv2.rectangle(target, (50, 50), (110, 110), (0, 0, 0), -1)
cv2.rectangle(target, (200, 150), (260, 210), (0, 0, 0), -1)
cv2.imwrite('test_target.png', target)
print("Created test_target.png")

# Perform matching
print("Performing matching...")
matches_count = matcher.match(target)

if matches_count < 0:
    print(f"Match failed with error code: {matches_count}")
    sys.exit(1)

print(f"Found {matches_count} matches")

# Display results
target_color = cv2.cvtColor(target, cv2.COLOR_GRAY2BGR)

for i in range(min(matches_count, matcher.maxCount)):
    result = matcher.results[i]
    if result.score > 0:
        points = np.array([
            [int(result.leftTopX), int(result.leftTopY)],
            [int(result.leftBottomX), int(result.leftBottomY)],
            [int(result.rightBottomX), int(result.rightBottomY)],
            [int(result.rightTopX), int(result.rightTopY)]
        ], np.int32)
        cv2.polylines(target_color, [points], True, (0, 255, 0), 2)
        cv2.putText(target_color, f"{result.score:.2f}", 
                   (int(result.leftTopX), int(result.leftTopY - 10)),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        print(f"Match {i+1}: Score={result.score:.2f}, Position=({int(result.centerX)}, {int(result.centerY)})")

# Save result
output_path = "demo_result.png"
cv2.imwrite(output_path, target_color)
print(f"Result saved to {output_path}")

print("Python demo completed successfully!")
print("Note: This demo creates test images instead of using a camera for simplicity.")