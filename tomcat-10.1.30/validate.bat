@echo off
chcp 65001 >nul

docker exec -it vulnerable-tomcat jcmd 1 GC.run
docker exec -it vulnerable-tomcat jcmd 1 GC.class_histogram > baseline_histogram.txt

set /p cont=Bạn có muốn continue không? (y/n): 
if /i "%cont%" neq "y" exit

docker exec -it vulnerable-tomcat jcmd 1 GC.run
docker exec -it vulnerable-tomcat jcmd 1 GC.class_histogram > after_histogram.txt

set /p heap=Bạn có muốn lấy heap dump không? (y/n): 
if /i "%heap%" eq "y" (
    docker exec -it vulnerable-tomcat jcmd 1 GC.heap_dump > after_attack.hprof
)