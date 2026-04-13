# ApexElite Windows Build

## Build executable
Run from project root:

```powershell
.\BUILD_EXE.bat
```

Artifacts:
- `releases\ApexElite.exe`
- `releases\ApexElite-Windows-x64.zip`

## Quick launch check
```powershell
Start-Process .\releases\ApexElite.exe
```

## Notes
- If Windows SmartScreen warns on first launch, use "More info" then "Run anyway" for local unsigned builds.
- Rebuild after major Python/code updates.
