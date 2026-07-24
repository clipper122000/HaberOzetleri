import os
import shutil

DLLS = [
    "libbrotlicommon.dll",
    "libbrotlidec.dll",
    "libbz2-1.dll",
    "libdatrie-1.dll",
    "libexpat-1.dll",
    "libffi-8.dll",
    "libfontconfig-1.dll",
    "libfreetype-6.dll",
    "libfribidi-0.dll",
    "libgcc_s_seh-1.dll",
    "libgio-2.0-0.dll",
    "libglib-2.0-0.dll",
    "libgmodule-2.0-0.dll",
    "libgobject-2.0-0.dll",
    "libgraphite2.dll",
    "libharfbuzz-0.dll",
    "libharfbuzz-subset-0.dll",
    "libiconv-2.dll",
    "libintl-8.dll",
    "libpango-1.0-0.dll",
    "libpangoft2-1.0-0.dll",
    "libpcre2-8-0.dll",
    "libpng16-16.dll",
    "libstdc++-6.dll",
    "libthai-0.dll",
    "libwinpthread-1.dll",
    "zlib1.dll"
]

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    msys_bin_dir = r"C:\msys64\mingw64\bin"
    msys_fonts_conf = r"C:\msys64\mingw64\etc\fonts\fonts.conf"
    
    target_gtk_dir = os.path.join(script_dir, "gtk_bin")
    target_fonts_dir = os.path.join(script_dir, "etc", "fonts")
    
    print("Creating target directories...")
    os.makedirs(target_gtk_dir, exist_ok=True)
    os.makedirs(target_fonts_dir, exist_ok=True)
    
    # 1. Copy DLLs
    print(f"Copying {len(DLLS)} DLLs from {msys_bin_dir} to {target_gtk_dir}...")
    copied_count = 0
    for dll in DLLS:
        source_path = os.path.join(msys_bin_dir, dll)
        dest_path = os.path.join(target_gtk_dir, dll)
        if os.path.exists(source_path):
            shutil.copy2(source_path, dest_path)
            copied_count += 1
        else:
            print(f"Warning: Source file does not exist: {source_path}")
            
    print(f"Successfully copied {copied_count}/{len(DLLS)} DLLs.")
    
    # 2. Copy fonts.conf
    print(f"Copying fonts.conf from {msys_fonts_conf} to {target_fonts_dir}...")
    if os.path.exists(msys_fonts_conf):
        shutil.copy2(msys_fonts_conf, os.path.join(target_fonts_dir, "fonts.conf"))
        print("Successfully copied fonts.conf.")
    else:
        print(f"Warning: fonts.conf not found at {msys_fonts_conf}")

if __name__ == "__main__":
    main()
