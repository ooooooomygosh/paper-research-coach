# Install (or update) the Paper Research Coach workbench. Windows PowerShell 5.1 or newer.
#
#   irm https://raw.githubusercontent.com/ooooooomygosh/paper-research-coach/main/scripts/install.ps1 | iex
#
# Same steps as install.sh: find the newest release (pre-releases included), download its wheel,
# check the SHA-256 against the release's SHA256SUMS, install it in its own environment with uv,
# pipx or a plain venv. No admin rights, no execution-policy change, no edits to your library.
#
# NOTE: this script mirrors the tested install.sh but has NOT been run on real Windows yet.
# If it fails, the manual steps in docs/QUICKSTART.md still work.
#
# Test hooks: $env:PRC_RELEASES_URL, $env:PRC_INSTALL_METHOD (uv|pipx|venv), $env:PRC_VENV_DIR

$ErrorActionPreference = "Stop"
$Repo = "ooooooomygosh/paper-research-coach"
$ReleasesUrl = if ($env:PRC_RELEASES_URL) { $env:PRC_RELEASES_URL } else { "https://api.github.com/repos/$Repo/releases?per_page=10" }
$VenvDir = if ($env:PRC_VENV_DIR) { $env:PRC_VENV_DIR } else { Join-Path $env:LOCALAPPDATA "PaperResearchCoach\venv" }

function Fail($message) {
    Write-Host ""
    Write-Host "没有安装成功 / Install failed: $message" -ForegroundColor Red
    throw $message
}
function Has($name) { return [bool](Get-Command $name -ErrorAction SilentlyContinue) }

Write-Host "Paper Research Coach · 安装 / Install"
$Temp = Join-Path ([System.IO.Path]::GetTempPath()) ("prc-install-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $Temp | Out-Null
try {
    # 1. The newest release that carries a wheel (the API lists newest first).
    Write-Host "· 查找最新版本 / Finding the newest release..."
    try { $releases = Invoke-RestMethod -Uri $ReleasesUrl -Headers @{ "User-Agent" = "prc-install"; "Accept" = "application/vnd.github+json" } }
    catch { Fail "无法连接 GitHub。请检查网络，或到 Releases 页面手动下载。/ Could not reach GitHub." }
    $wheelAsset = $null
    foreach ($release in $releases) {
        if ($release.draft) { continue }
        $wheelAsset = $release.assets | Where-Object { $_.name -match '^paper_research_coach-[^-]+-py3-none-any\.whl$' } | Select-Object -First 1
        if ($wheelAsset) { break }
    }
    if (-not $wheelAsset) { Fail "没有找到可安装的发布版本。/ No installable release found." }
    $wheelName = $wheelAsset.name
    $namePattern = [regex]::Escape($wheelName) + '$'
    $sumsUrl = $wheelAsset.browser_download_url -replace $namePattern, 'SHA256SUMS'
    $version = ($wheelName -replace '^paper_research_coach-', '') -replace '-py3-none-any\.whl$', ''
    Write-Host "  最新版本 / Newest: $version"

    # 2. Download and verify.
    Write-Host "· 下载并校验 / Downloading and verifying..."
    $wheel = Join-Path $Temp $wheelName
    Invoke-WebRequest -Uri $wheelAsset.browser_download_url -OutFile $wheel -UseBasicParsing
    try { Invoke-WebRequest -Uri $sumsUrl -OutFile (Join-Path $Temp "SHA256SUMS") -UseBasicParsing }
    catch { Fail "这个版本没有校验文件（SHA256SUMS），为安全起见不安装。/ This release has no SHA256SUMS; refusing to install unverified code." }
    $line = Get-Content (Join-Path $Temp "SHA256SUMS") | Where-Object { $_ -match ([regex]::Escape($wheelName) + '$') } | Select-Object -First 1
    if (-not $line) { Fail "校验文件里没有这个安装包。/ SHA256SUMS does not list this wheel." }
    $expected = ($line -split '\s+')[0].ToLower()
    $actual = (Get-FileHash -Algorithm SHA256 -Path $wheel).Hash.ToLower()
    if ($expected -ne $actual) { Fail "校验值不符，已停止。/ Checksum mismatch; nothing was installed." }

    # 3. Pick an installer: uv (it can also fetch Python), pipx, or a plain venv.
    $method = $env:PRC_INSTALL_METHOD
    if (-not $method) {
        if (Has "uv") { $method = "uv" }
        elseif (Has "pipx") { $method = "pipx" }
        elseif ((Has "py") -or (Has "python")) { $method = "venv" }
        else {
            Fail ("没有找到 uv、pipx 或 Python。最省事：先安装 uv（它会自动准备 Python），再重新运行本脚本：`n" +
                  "  powershell -ExecutionPolicy ByPass -c `"irm https://astral.sh/uv/install.ps1 | iex`"`n" +
                  "Easiest: install uv (it fetches Python for you) and run this again.")
        }
    }

    Write-Host "· 安装 / Installing with $method..."
    $prc = $null
    switch ($method) {
        "uv" {
            & uv tool install --force --python 3.12 $wheel
            if ($LASTEXITCODE -ne 0) { Fail "uv 安装失败 / uv install failed." }
            & uv tool update-shell 2>$null | Out-Null
            $prc = Join-Path ((& uv tool dir --bin).Trim()) "prc.exe"
        }
        "pipx" {
            & pipx install --force $wheel
            if ($LASTEXITCODE -ne 0) { Fail "pipx 安装失败 / pipx install failed." }
            & pipx ensurepath 2>$null | Out-Null
            $prc = Join-Path ((& pipx environment --value PIPX_BIN_DIR).Trim()) "prc.exe"
        }
        "venv" {
            New-Item -ItemType Directory -Force -Path (Split-Path $VenvDir) | Out-Null
            if (Has "py") { & py -3 -m venv $VenvDir } else { & python -m venv $VenvDir }
            if ($LASTEXITCODE -ne 0) { Fail "无法创建 Python 虚拟环境（需要 Python 3.10 或更新版本）。/ Could not create a venv (Python 3.10+ required)." }
            & (Join-Path $VenvDir "Scripts\python.exe") -m pip install --quiet --upgrade $wheel
            if ($LASTEXITCODE -ne 0) { Fail "venv 安装失败 / venv install failed." }
            $prc = Join-Path $VenvDir "Scripts\prc.exe"
            $scripts = Join-Path $VenvDir "Scripts"
            $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
            if (($userPath -split ';') -notcontains $scripts) {
                [Environment]::SetEnvironmentVariable("Path", ($userPath.TrimEnd(';') + ";" + $scripts), "User")
            }
        }
        default { Fail "未知的安装方式：$method" }
    }
    if (-not (Test-Path $prc)) { Fail "安装完成，但找不到 prc 程序。/ Installed, but the prc command was not found." }
    Write-Host "  已安装 / Installed: $(& $prc --version)"
    # Skill copies made earlier by `prc install-skill` follow this version too.
    try { & $prc install-skill --sync *> $null } catch { }
    Write-Host ""
    Write-Host "完成。/ Done."
    Write-Host ""
    Write-Host "  打开工作台 / Open the workbench:   prc"
    Write-Host "  桌面图标 / Desktop launcher:        prc shortcut"
    Write-Host "  更新 / Updates:                     自动（后台校验并安装）；也可以运行 prc update / automatic, or prc update"
    Write-Host ""
    Write-Host "如果提示找不到 prc，请重新打开 PowerShell。/ If prc is not found, open a new PowerShell window."
    Write-Host "Claude Code 用户：在 Claude Code 里运行 /plugin marketplace add $Repo 安装 Skill。"
}
finally {
    Remove-Item -Recurse -Force $Temp -ErrorAction SilentlyContinue
}
