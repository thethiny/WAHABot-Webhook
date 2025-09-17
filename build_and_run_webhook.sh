docker build -t waha_webhook .

docker run -it --rm --name waha_webhook -p 13001:13001 --env-file .env waha_webhook