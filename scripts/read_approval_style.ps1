# 只读本机WPS实际显示样式；不返回业务单元格值，不修改原母版。
param([Parameter(Mandatory=$true)][string]$TemplatePath)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$hadEt=@(Get-Process et -ErrorAction SilentlyContinue).Count -gt 0
$app=New-Object -ComObject ket.Application
$before=$app.Workbooks.Count;$alerts=$app.DisplayAlerts;$book=$null;$security=$null
try{
    $app.DisplayAlerts=$false
    try{$security=$app.AutomationSecurity;$app.AutomationSecurity=3}catch{}
    $book=$app.Workbooks.Open($TemplatePath,0,$true)
    $sheets=@{}
    foreach($name in @('常规商品','鲜食')){
        $sheet=$book.Worksheets.Item($name);$columns=if($name -eq '鲜食'){17}else{16};$parts=@{}
        foreach($part in @('header','body')){
            $row=if($part -eq 'header'){1}else{2};$cells=@()
            for($c=1;$c -le $columns;$c++){
                $cell=$sheet.Cells.Item($row,$c)
                $cells+=@{fill=[int]$cell.Interior.Color;font=[int]$cell.Font.Color}
            }
            $parts[$part]=$cells
        }
        $sheets[$name]=$parts
    }
    @{version=1;sheets=$sheets;read_only=$true;no_business_values=$true} | ConvertTo-Json -Depth 8 -Compress
}finally{
    if($null -ne $book){$book.Close($false)}
    if($null -ne $security){try{$app.AutomationSecurity=$security}catch{}}
    $app.DisplayAlerts=$alerts
    if(-not $hadEt -and $before -eq 0){$app.Quit()}
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($app)
}
