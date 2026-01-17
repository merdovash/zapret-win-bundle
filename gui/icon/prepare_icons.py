#!/usr/bin/env python3
"""
Script to prepare icon files from icon.jpg
Creates optimized icon sizes for Windows taskbar, window, and tray icons
"""

import sys
from pathlib import Path
from PIL import Image

def prepare_icons():
    """Prepare icon files from icon.jpg"""
    script_dir = Path(__file__).parent
    icon_jpg = script_dir / "icon.jpg"
    
    if not icon_jpg.exists():
        print(f"Error: {icon_jpg} not found!")
        return False
    
    print(f"Loading {icon_jpg}...")
    try:
        # Load original image
        original = Image.open(icon_jpg)
        
        # Convert to RGBA if needed
        if original.mode != 'RGBA':
            print("Converting to RGBA...")
            original = original.convert('RGBA')
        
        print(f"Original size: {original.size}")
        
        # Define sizes to create
        sizes = [
            (16, 16, "icon_16x16.png"),
            (32, 32, "icon_32x32.png"),
            (48, 48, "icon_48x48.png"),
            (64, 64, "icon_64x64.png"),
            (256, 256, "icon_256x256.png"),
        ]
        
        # Create individual PNG files for each size
        print("\nCreating optimized icon sizes...")
        for width, height, filename in sizes:
            output_path = script_dir / filename
            
            # Use LANCZOS for high-quality downscaling
            resized = original.resize((width, height), Image.Resampling.LANCZOS)
            resized.save(output_path, format='PNG', optimize=True)
            print(f"  Created {filename} ({width}x{height})")
        
        # Create multi-size ICO file
        print("\nCreating multi-size ICO file...")
        ico_path = script_dir / "icon.ico"
        
        # Create ICO with multiple sizes
        # PIL can create multi-size ICO files
        ico_sizes = [(16, 16), (32, 32), (48, 48), (256, 256)]
        
        # Create resized images for each size
        ico_images = []
        for size in ico_sizes:
            resized = original.resize(size, Image.Resampling.LANCZOS)
            ico_images.append(resized)
        
        # Save as ICO - use the largest size as base
        largest = original.resize((256, 256), Image.Resampling.LANCZOS)
        largest.save(ico_path, format='ICO', sizes=ico_sizes)
        print(f"  Created icon.ico with sizes: {', '.join([f'{w}x{h}' for w, h in ico_sizes])}")
        
        print("\nIcon preparation complete!")
        print(f"  Generated files in: {script_dir}")
        return True
        
    except Exception as e:
        print(f"Error preparing icons: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = prepare_icons()
    sys.exit(0 if success else 1)

