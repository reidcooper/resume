### Preview

![Resume Page 1](/resume_preview_p1.png)

![Resume Page 2](/resume_preview_p2.png)

### Build using Docker

```sh
docker build -t latex .
docker run --rm -i -v "$PWD":/data latex pdflatex reid_cooper_resume.tex
convert -background white -alpha background -alpha off -density 600 'reid_cooper_resume.pdf[0]' -resize 25% resume_preview_p1.png
convert -background white -alpha background -alpha off -density 600 'reid_cooper_resume.pdf[1]' -resize 25% resume_preview_p2.png
```

### License

Format is MIT but all the data is owned by Reid Cooper.
