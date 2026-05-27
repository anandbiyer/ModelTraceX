Attribute VB_Name = "EtlMacro"
' VBA language fixture: read the RawData sheet, compute a ratio, write the KPI sheet.
Sub BuildKpi()
    Dim wsIn As Worksheet, wsOut As Worksheet
    Set wsIn = ThisWorkbook.Sheets("RawData")
    Set wsOut = ThisWorkbook.Sheets("KPI")
    Dim i As Long
    For i = 2 To wsIn.Cells(wsIn.Rows.Count, 1).End(xlUp).Row
        wsOut.Cells(i, 1).Value = wsIn.Cells(i, 1).Value
        wsOut.Cells(i, 2).Value = wsIn.Cells(i, 2).Value / wsIn.Cells(i, 3).Value
    Next i
End Sub
