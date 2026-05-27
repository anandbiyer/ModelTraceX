Attribute VB_Name = "Export"
' Multilang pipeline — step 4 (VBA). Reads staging.scored, writes the Report sheet.
Sub ExportScores()
    Dim scored As Worksheet, report As Worksheet
    Set scored = Worksheets("scored")
    Set report = Worksheets("Report")
    Dim r As Long
    For r = 2 To scored.UsedRange.Rows.Count
        report.Cells(r, 1).Value = scored.Cells(r, 1).Value
        report.Cells(r, 2).Value = scored.Cells(r, 4).Value
    Next r
End Sub
