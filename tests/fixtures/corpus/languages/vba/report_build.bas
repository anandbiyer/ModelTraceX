Attribute VB_Name = "ReportBuild"
' VBA language fixture: pull from the Orders sheet, filter by threshold, write Summary.
Sub BuildReport()
    Dim src As Worksheet, dst As Worksheet
    Set src = Worksheets("Orders")
    Set dst = Worksheets("Summary")
    Dim r As Long, total As Double
    For r = 2 To src.UsedRange.Rows.Count
        If src.Cells(r, 3).Value > 1000 Then
            total = total + src.Cells(r, 3).Value
        End If
    Next r
    dst.Range("B1").Value = total
End Sub
