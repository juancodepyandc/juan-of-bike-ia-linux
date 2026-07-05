@echo off
chcp 65001 1>NUL 2>NUL
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
if errorlevel 1 ( echo VCVARS_FAILED & exit /b 1 )
set "CUDA_HOME=C:\Users\Juan\Desktop\ia\AuroraIA-v2\application\_cuda_home"
set "CUDA_PATH=%CUDA_HOME%"
set "PATH=%CUDA_HOME%\bin;%CUDA_HOME%\nvvm\bin;%PATH%"
set "TORCH_CUDA_ARCH_LIST=8.0;8.6;8.9;9.0;12.0"
set "DISTUTILS_USE_SDK=1"
set "NVCC_PREPEND_FLAGS=-allow-unsupported-compiler"
set "PYTHONIOENCODING=utf-8"
set "PY=C:\Users\Juan\AppData\Local\Programs\Python\Python312\python.exe"
echo === nvcc check ===
nvcc --version

echo === [1/2] build mesh_inpaint_processor (DifferentiableRenderer, pybind11, no CUDA) ===
cd /d "C:\Users\Juan\AppData\Local\Temp\hy3d21-src\hy3dpaint\DifferentiableRenderer"
if exist build rmdir /s /q build
del /q mesh_inpaint_processor.*.pyd 1>NUL 2>NUL
"%PY%" -m pip install -q pybind11 numpy setuptools
"%PY%" setup.py build_ext --inplace
if errorlevel 1 ( echo MESH_INPAINT_BUILD_FAILED & goto crbuild )
for %%f in (mesh_inpaint_processor.*.pyd) do (
  echo built %%f
  copy /y "%%f" "C:\Users\Juan\AppData\Local\Programs\Python\Python312\Lib\site-packages\" 1>NUL
)
"%PY%" -c "import mesh_inpaint_processor; print('MESH_INPAINT_IMPORT_OK')"

:crbuild
echo === [2/2] build custom_rasterizer 2.1 (CUDA, sm_120) ===
cd /d "C:\Users\Juan\AppData\Local\Temp\hy3d21-src\hy3dpaint\custom_rasterizer"
if exist build rmdir /s /q build
"%PY%" -m pip install --no-build-isolation --force-reinstall --no-deps .
if errorlevel 1 ( echo CUSTOM_RASTERIZER_BUILD_FAILED & exit /b 1 )
"%PY%" -c "import torch; import custom_rasterizer_kernel; import custom_rasterizer; print('CUSTOM_RASTERIZER_IMPORT_OK')"
echo === DONE exit %errorlevel% ===
