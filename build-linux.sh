#!/bin/sh

now=$(date +'%Y-%m-%d_%T')
go build -tags linux -o adsyncd -ldflags "-X main.version=`cat VERSION` -X main.buildTime=$now -X main.buildHash=`git rev-parse HEAD`" ./main-linux.go