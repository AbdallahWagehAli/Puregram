@echo ON
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" -vcvars_ver=14.44
if errorlevel 1 ( echo VCVARS_FAILED & exit /b 1 )
set "PATH=%SystemRoot%\System32;%SystemRoot%;%SystemRoot%\System32\Wbem;%PATH%"
rem configure.bat uses %~dp0 to find configure.py, and paths are script-relative,
rem so calling it by full path works regardless of the current directory.
rem Puregram Desktop uses its OWN my.telegram.org app, separate from Android's.
:: Puregram: the Telegram API credentials are NOT committed. Copy
:: api_credentials.example.bat to api_credentials.bat (gitignored) and put your
:: own pair from https://my.telegram.org in it. See BUILDING.md.
if exist "%~dp0api_credentials.bat" call "%~dp0api_credentials.bat"
if not defined TDESKTOP_API_ID ( echo MISSING api_credentials.bat - see BUILDING.md & exit /b 1 )
call "%~dp0tdesktop\Telegram\configure.bat" x64 -D TDESKTOP_API_ID=%TDESKTOP_API_ID% -D TDESKTOP_API_HASH=%TDESKTOP_API_HASH%
echo CONFIGURE_EXIT=%errorlevel%
