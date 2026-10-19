$ErrorActionPreference = 'SilentlyContinue'
$steamRoots = @()
foreach ($key in @('HKCU:\Software\Valve\Steam','HKLM:\SOFTWARE\WOW6432Node\Valve\Steam','HKLM:\SOFTWARE\Valve\Steam')) {
    $p = Get-ItemProperty -LiteralPath $key
    if ($p.SteamPath) { $steamRoots += ($p.SteamPath -replace '/', '\') }
    if ($p.InstallPath) { $steamRoots += ($p.InstallPath -replace '/', '\') }
}
$libraries = [System.Collections.Generic.List[string]]::new()
foreach ($root in ($steamRoots | Select-Object -Unique)) {
    $libraries.Add($root)
    $vdf = Join-Path $root 'steamapps\libraryfolders.vdf'
    if (Test-Path -LiteralPath $vdf) {
        $content = Get-Content -LiteralPath $vdf -Raw
        foreach ($m in [regex]::Matches($content, '(?m)^\s*"path"\s+"((?:\\\\|[^"\\])*)"')) {
            $libraries.Add(($m.Groups[1].Value -replace '\\\\','\'))
        }
        foreach ($m in [regex]::Matches($content, '(?m)^\s*"\d+"\s+"((?:\\\\|[^"\\])*)"')) {
            $libraries.Add(($m.Groups[1].Value -replace '\\\\','\'))
        }
    }
}
foreach ($library in ($libraries | Select-Object -Unique)) {
    $candidate = Join-Path $library 'steamapps\common\SteamVR\bin\win64\vrpathreg.exe'
    if (Test-Path -LiteralPath $candidate) { Write-Output $candidate; exit 0 }
}
exit 1
