$ErrorActionPreference = "Stop"

$baseUrl = "http://localhost:8000"
$endpoint = "$baseUrl/api/v1/legal-graphrag/v1_1/chat/"

$cases = @(
  @{ id = 1; query = "IVA entradas teatro"; expected = @(10) },
  @{ id = 2; query = "IVA para entradas de concierto"; expected = @(10) },
  @{ id = 3; query = "Tipo IVA para museos y exposiciones"; expected = @(10) },
  @{ id = 4; query = "IVA para entradas de circo"; expected = @(10) },
  @{ id = 5; query = "IVA servicios de artistas a organizador"; expected = @(10) },
  @{ id = 6; query = "IVA aplicable a interprete contratado por organizador"; expected = @(10) },
  @{ id = 7; query = "IVA servicios de director tecnico de teatro"; expected = @(10) },
  @{ id = 8; query = "IVA a productor de cine que presta servicios a organizador"; expected = @(10) },
  @{ id = 9; query = "IVA para libros"; expected = @(4) },
  @{ id = 10; query = "IVA para revistas"; expected = @(4) },
  @{ id = 11; query = "IVA para periodico"; expected = @(4) },
  @{ id = 12; query = "IVA para partituras"; expected = @(4) },
  @{ id = 13; query = "IVA general servicios de consultoria"; expected = @(21) },
  @{ id = 14; query = "Tipo IVA general"; expected = @(21) },
  @{ id = 15; query = "IVA aplicable a servicios digitales generales"; expected = @(21) },
  @{ id = 16; query = "IVA aplicable a un servicio sin reduccion"; expected = @(21) },
  @{ id = 17; query = "IVA para entradas de biblioteca"; expected = @(10) },
  @{ id = 18; query = "IVA para exposiciones"; expected = @(10) },
  @{ id = 19; query = "IRPF retencion consejero administrador con cifra de negocios superior a 100000"; expected = @(35) },
  @{ id = 20; query = "IRPF retencion consejero administrador con cifra de negocios inferior a 100000"; expected = @(19) },
  @{ id = 21; query = "IRPF retencion consejero administrador cifra de negocios 120000"; expected = @(35) },
  @{ id = 22; query = "IRPF retencion consejero administrador cifra de negocios 80000"; expected = @(19) },
  @{ id = 23; query = "IRPF retencion actividad profesional inicio de actividad"; expected = @(7) },
  @{ id = 24; query = "IRPF retencion actividad profesional nuevo inicio"; expected = @(7) },
  @{ id = 25; query = "IRPF retencion actividad profesional no es inicio"; expected = @(15) },
  @{ id = 26; query = "IRPF retencion actividad profesional con mas de 3 anos"; expected = @(15) },
  @{ id = 27; query = "IRPF retencion cesion de derecho de imagen"; expected = @(24) },
  @{ id = 28; query = "IRPF retencion arrendamiento inmuebles urbanos"; expected = @(19) },
  @{ id = 29; query = "IRPF retencion consejero administrador"; expected = @() },
  @{ id = 30; query = "IRPF retencion actividad profesional"; expected = @() }
)

function Extract-Percentages([string]$text) {
  if (-not $text) { return @() }
  $matches = [regex]::Matches($text, '\b(\d{1,3})\s*%')
  $values = @()
  foreach ($match in $matches) {
    $value = $match.Groups[1].Value
    if ($value -match '^\d+$') {
      $values += [int]$value
    }
  }
  return $values
}

$results = @()

foreach ($case in $cases) {
  $sessionId = [guid]::NewGuid().ToString()
  $body = @{
    query = $case.query
    session_id = $sessionId
  } | ConvertTo-Json

  try {
    $response = Invoke-RestMethod -Method Post -Uri $endpoint -ContentType "application/json" -Body $body -TimeoutSec 120
    $answer = $response.answer
    $found = Extract-Percentages $answer
    $expected = $case.expected
    $missing = @()
    foreach ($rate in $expected) {
      if ($found -notcontains $rate) {
        $missing += $rate
      }
    }
    $extra = @()
    foreach ($rate in $found) {
      if ($expected -notcontains $rate) {
        $extra += $rate
      }
    }
    $ok = ($missing.Count -eq 0) -and ($extra.Count -eq 0)
    if ($expected.Count -eq 0) {
      $ok = ($found.Count -eq 0)
    }

    $results += [pscustomobject]@{
      id = $case.id
      query = $case.query
      expected = ($expected -join ",")
      found = ($found -join ",")
      ok = $ok
      answer_preview = ($answer -replace '\s+', ' ').Substring(0, [Math]::Min(160, ($answer -replace '\s+', ' ').Length))
    }
  } catch {
    $results += [pscustomobject]@{
      id = $case.id
      query = $case.query
      expected = ($case.expected -join ",")
      found = ""
      ok = $false
      answer_preview = "ERROR: $($_.Exception.Message)"
    }
  }
}

$passed = ($results | Where-Object { $_.ok }).Count
$failed = $results.Count - $passed

$results | Sort-Object id | Format-Table -AutoSize
Write-Host ""
Write-Host ("Passed: {0} / {1}" -f $passed, $results.Count)
Write-Host ("Failed: {0}" -f $failed)

if ($failed -gt 0) {
  Write-Host ""
  Write-Host "Failures:"
  $results | Where-Object { -not $_.ok } | ForEach-Object {
    Write-Host ("- #{0} {1} | expected [{2}] found [{3}]" -f $_.id, $_.query, $_.expected, $_.found)
  }
}
