#!/usr/bin/env bash

docker build -t sb2nov/latex .
docker run --rm -i -v "$PWD":/data sb2nov/latex pdflatex reid_cooper_resume.tex
convert -background white -alpha background -alpha off -density 600 reid_cooper_resume.pdf -resize 25% resume_preview.png
pandoc reid_cooper_resume.md -o reid_cooper_resume.docx
