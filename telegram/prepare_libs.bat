@echo ON
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" -vcvars_ver=14.44
if %errorlevel% neq 0 ( echo VCVARS_FAILED & exit /b 1 )
cd /d "C:\Users\lap_shop\Desktop\Puregram\telegram"
call tdesktop\Telegram\build\prepare\win.bat
echo PREPARE_EXIT=%errorlevel%
