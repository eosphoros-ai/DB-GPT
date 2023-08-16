Docker Compose
==================================

#### Run with docker compose

```bash
$ docker compose up -d
```

Output should look something like the following:
```
[+] Building 0.0s (0/0)
[+] Running 2/2
 ✔ Container db-gpt-db-1         Started                                                                                                                                                                                          0.4s
 ✔ Container db-gpt-webserver-1  Started
```

You can see log with command:

```bash
$ docker logs db-gpt-webserver-1 -f
```

Open http://localhost:5000 with your browser to see the product.

You can open docker-compose.yml in the project root directory to see more details.
