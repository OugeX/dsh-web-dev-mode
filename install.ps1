# DSH Web Dev Mode · 一键安装（Windows PowerShell）
$ErrorActionPreference = "Stop"

$DshHome = if ($env:DSH_HOME) { $env:DSH_HOME } else { Join-Path $env:USERPROFILE ".dsh" }
$Src = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "▶ 安装目标：$DshHome"

if (-not (Test-Path $DshHome)) {
    Write-Host "❌ 找不到 $DshHome"
    Write-Host "   请先安装 DSH 并至少运行一次，或设置 `$env:DSH_HOME 后再执行"
    exit 1
}

$PresetRoot = Join-Path $DshHome ".agent-presets"
$SkillsRoot = Join-Path $DshHome "skills"
New-Item -ItemType Directory -Force -Path $PresetRoot, $SkillsRoot | Out-Null

# ── 1. preset（含备份）──────────────────────────────────────────
$PresetDst = Join-Path $PresetRoot "web-dev"
if (Test-Path $PresetDst) {
    $Bak = "$PresetDst.bak.$(Get-Date -Format 'yyyyMMddHHmmss')"
    Move-Item $PresetDst $Bak
    Write-Host "  已备份原 preset → $Bak"
}
Copy-Item -Recurse -Force (Join-Path $Src "presets\web-dev") $PresetDst
Write-Host "▶ preset 已安装"

# ── 2. skills ───────────────────────────────────────────────────
$count = 0
Get-ChildItem (Join-Path $Src "skills") -Directory | Where-Object {
    Test-Path (Join-Path $_.FullName "SKILL.md")
} | ForEach-Object {
    $dest = Join-Path $SkillsRoot $_.Name
    if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
    Copy-Item -Recurse -Force $_.FullName $dest
    $count++
}
Write-Host "▶ skills 已安装：$count 个"

# ── 3. 安装后校验 ────────────────────────────────────────────────
Write-Host "▶ 校验"
$fail = $false

$cordis = Get-Content (Join-Path $PresetDst "agent.cordis.yml") -Raw
$presetYml = Get-Content (Join-Path $PresetDst "preset.yml") -Raw
if ($cordis -match "id: persona" -and $presetYml -match "Web") {
    Write-Host "   OK preset 结构正常"
} else {
    Write-Host "   FAIL preset 结构异常"; $fail = $true
}

$ok = 0
Get-ChildItem (Join-Path $Src "skills") -Directory | ForEach-Object {
    $name = $_.Name
    $f = Join-Path $SkillsRoot "$name\SKILL.md"
    if (Test-Path $f) {
        $head = Get-Content $f -TotalCount 1
        $body = Get-Content $f -Raw
        if ($head -eq "---" -and $body -match "(?m)^name: $([regex]::Escape($name))$") {
            $script:ok++
        } else {
            Write-Host "   FAIL $name frontmatter 异常"; $script:fail = $true
        }
    } else {
        Write-Host "   FAIL $name 缺失"; $script:fail = $true
    }
}
Write-Host "   OK skills frontmatter 合格：$ok/$count"

if ($fail) {
    Write-Host ""
    Write-Host "⚠ 校验有失败项，请检查上面的输出"
    exit 1
}

# ── 4. 提示 ─────────────────────────────────────────────────────
Write-Host ""
Write-Host "安装完成"
Write-Host ""
Write-Host "下一步："
Write-Host "  1. 重启 DSH                （skills 已热加载，但 preset 需要重启才出现在模式列表）"
Write-Host "  2. 模式下拉里选择「Web开发模式」"
Write-Host "  3. 设为默认（可选）：编辑 $DshHome\settings.yaml"
Write-Host "       agent-presets:"
Write-Host "         default: web-dev"
Write-Host ""
Write-Host "验证：重启后新开对话，说「新建一个后台管理系统」，"
Write-Host "      应先输出一行「技能计划：...」，再问 5 个澄清问题。"
