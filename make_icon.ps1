# Makes data/icon.png (512x512, square) from any photo.
#
#   powershell -ExecutionPolicy Bypass -File make_icon.ps1 "C:\path\to\photo.jpg"
#
# Center-crops to a square (biased toward the TOP so a face/subject near
# the top is kept), then resizes to 512x512.

param(
    [Parameter(Mandatory = $true)] [string] $Source,
    [int]    $Size    = 512,
    [double] $TopBias = 0.15   # 0 = crop from very top, 0.5 = centered
)

Add-Type -AssemblyName System.Drawing

$src = [System.Drawing.Image]::FromFile((Resolve-Path $Source))
try {
    $side = [Math]::Min($src.Width, $src.Height)
    $x = [int](($src.Width  - $side) / 2)
    $y = [int](($src.Height - $side) * $TopBias)

    $square = New-Object System.Drawing.Bitmap($side, $side)
    $g = [System.Drawing.Graphics]::FromImage($square)
    $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $g.DrawImage($src,
        (New-Object System.Drawing.Rectangle(0, 0, $side, $side)),
        (New-Object System.Drawing.Rectangle($x, $y, $side, $side)),
        [System.Drawing.GraphicsUnit]::Pixel)
    $g.Dispose()

    $out = New-Object System.Drawing.Bitmap($Size, $Size)
    $g2 = [System.Drawing.Graphics]::FromImage($out)
    $g2.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $g2.DrawImage($square, 0, 0, $Size, $Size)
    $g2.Dispose()

    $dst = Join-Path $PSScriptRoot 'data\icon.png'
    New-Item -ItemType Directory -Force -Path (Split-Path $dst) | Out-Null
    $out.Save($dst, [System.Drawing.Imaging.ImageFormat]::Png)
    Write-Host "wrote $dst  ($Size x $Size)"
}
finally {
    $src.Dispose()
}
