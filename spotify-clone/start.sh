#!/bin/bash
cd "$(dirname "$0")"
if [ ! -d "node_modules" ]; then
  echo "初回起動: パッケージをインストール中..."
  npm install
fi
npm start
