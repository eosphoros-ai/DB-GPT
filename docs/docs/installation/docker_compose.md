# Docker-Compose Deployment

## Run via Docker-Compose

This example requires you previde a valid API key for the SiliconFlow API. You can obtain one by signing up at [SiliconFlow](https://siliconflow.cn/) and creating an API key at [API Key](https://cloud.siliconflow.cn/account/ak).


```bash
SILICONFLOW_API_KEY=${SILICONFLOW_API_KEY} docker compose up -d
```

You will see the following output if the deployment is successful.
```bash
[+] Running 3/3
 ✔ Network dbgptnet              Created                                            0.0s 
 ✔ Container db-gpt-db-1         Started                                            0.2s 
 ✔ Container db-gpt-webserver-1  Started                                            0.2s 
```


## View log
```bash
docker logs db-gpt-webserver-1 -f
```

:::info note

For more configuration content, you can view the `docker-compose.yml` file
:::


## Visit
Open the browser and visit [http://localhost:5670](http://localhost:5670)
