$ErrorActionPreference = "Stop"

function Write-Utf8NoBom([string]$Path,[string]$Text){
  $enc = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllText($Path,$Text,$enc)
}

if (!(Test-Path "alembic.ini")) { throw "alembic.ini not found. cd to backend root." }

$repo = (Get-Location).Path

# --- Robust versions dir detection (always returns an array) ---
$paths = @()
foreach ($rel in @('alembic\versions','migrations\versions','app\alembic\versions')) {
  $p = Join-Path $repo $rel
  if (Test-Path $p) { $paths += (Resolve-Path $p).Path }
}
if ($paths.Count -eq 0) {
  $guess = Get-ChildItem -Directory -Recurse -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -eq 'versions' -and (Get-ChildItem $_.FullName -Filter *.py -ErrorAction SilentlyContinue) } |
    Select-Object -First 1
  if (-not $guess) { throw "Could not find Alembic versions directory." }
  $versionsDir = $guess.FullName
} else {
  $versionsDir = $paths[0]
}

Write-Host "Alembic versions dir: $versionsDir"

# --- Gather rev graph ---
$allRevs = New-Object System.Collections.Generic.HashSet[string]
$allDown = New-Object System.Collections.Generic.HashSet[string]
$files = Get-ChildItem -Path $versionsDir -Filter *.py -File
if ($files.Count -eq 0) { throw "No migration files found in $versionsDir" }

$rxRev  = [regex]'revision\s*=\s*["'']([0-9a-fA-F]+)["'']'
$rxDown = [regex]'down_revision\s*=\s*(.+)'

foreach ($f in $files) {
  $txt = [System.IO.File]::ReadAllText($f.FullName)
  $mRev = $rxRev.Match($txt); if ($mRev.Success) { [void]$allRevs.Add($mRev.Groups[1].Value) }
  $mDown = $rxDown.Match($txt)
  if ($mDown.Success) {
    $rhs = $mDown.Groups[1].Value.Trim()
    if ($rhs -ne 'None') {
      foreach ($m in [regex]::Matches($rhs, '["'']([0-9a-fA-F]+)["'']')) { [void]$allDown.Add($m.Groups[1].Value) }
    }
  }
}

$heads = @($allRevs.Where({ -not $allDown.Contains($_) }))
Write-Host "Detected heads: $($heads -join ', ')"

if ($heads.Count -le 1) {
  Write-Host "Nothing to merge. If deploy still errors, redeploy." -ForegroundColor Green
} else {
  Write-Host "Multiple heads detected, creating merge revision..." -ForegroundColor Yellow

  $rev  = ([Guid]::NewGuid().ToString('N')).Substring(0,12)
  $slug = 'merge_heads'
  $filename = Join-Path $versionsDir ("{0}_{1}.py" -f $rev,$slug)
  $now = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
  $downTuple = ($heads | ForEach-Object { "'$_'" }) -join ', '

  $merge = @"
\"\"\"merge heads to unify migration graph

Revision ID: $rev
Revises: $($heads -join ', ')
Create Date: $now
\"\"\"
from alembic import op
import sqlalchemy as sa

revision = "$rev"
down_revision = ($downTuple,)
branch_labels = None
depends_on = None

def upgrade():
    pass

def downgrade():
    pass
"@

  Write-Utf8NoBom $filename $merge
  Write-Host "Created merge revision: $filename" -ForegroundColor Green

  # Cleanup common backups so they don't pollute commits
  $trash = @('alembic\env.py.bak','Dockerfile.bak','requirements.txt.bak','app\main.py.bak') |
           ForEach-Object { Join-Path $repo $_ } | Where-Object { Test-Path $_ }
  foreach ($t in $trash) { try { Write-Host "Removing $t"; Remove-Item -Force $t } catch {} }

  # Commit & push on the right branch
  $branch = (& git rev-parse --abbrev-ref HEAD) 2>$null
  if (-not $branch -or $branch -eq 'HEAD') { $branch = 'feature/initial-backend-clean' }
  git add -A
  try { & git commit -m "DB: alembic merge heads ($($heads -join ', '))" | Out-Null } catch { Write-Host "No changes to commit." }
  & git push -u origin $branch
  Write-Host "`nPushed to $branch." -ForegroundColor Cyan
}

Write-Host "`nNow redeploy your Render Docker service. Alembic should run cleanly." -ForegroundColor Yellow
