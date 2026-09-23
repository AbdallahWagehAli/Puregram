@echo ON
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" -vcvars_ver=14.44
if errorlevel 1 ( echo VCVARS_FAILED & exit /b 1 )
set "PATH=%SystemRoot%\System32;%SystemRoot%;%SystemRoot%\System32\Wbem;C:\Program Files\CMake\bin;%PATH%"
cmake --build "C:\Users\lap_shop\Desktop\Puregram\telegram\tdesktop\out" --config Release --target Telegram --parallel 8
echo BUILD_EXIT=%errorlevel%
