import asyncio
from typing import Any, Callable, List

from dbgpt.model.base import ModelInstance, WorkerApplyOutput, WorkerSupportedModel
from dbgpt.model.cluster.base import (
    WORKER_MANAGER_SERVICE_NAME,
    WORKER_MANAGER_SERVICE_TYPE,
    WorkerApplyRequest,
    WorkerStartupRequest,
)
from dbgpt.model.cluster.registry import ModelRegistry
from dbgpt.model.cluster.worker.manager import LocalWorkerManager, WorkerRunData, logger
from dbgpt.model.cluster.worker.remote_worker import RemoteModelWorker
from dbgpt.model.parameter import WorkerType


class RemoteWorkerManager(LocalWorkerManager):
    def __init__(self, model_registry: ModelRegistry = None) -> None:
        super().__init__(model_registry=model_registry)

    async def start(self):
        for listener in self.start_listeners:
            if asyncio.iscoroutinefunction(listener):
                await listener(self)
            else:
                listener(self)

    async def stop(self, ignore_exception: bool = False):
        pass

    async def _fetch_from_worker(
        self,
        worker_run_data: WorkerRunData,
        endpoint: str,
        method: str = "GET",
        json: dict = None,
        params: dict = None,
        additional_headers: dict = None,
        success_handler: Callable = None,
        error_handler: Callable = None,
    ) -> Any:
        # Lazy import to avoid high time cost
        import httpx

        url = worker_run_data.worker.worker_addr + endpoint
        headers = {**worker_run_data.worker.headers, **(additional_headers or {})}
        timeout = worker_run_data.worker.timeout

        async with httpx.AsyncClient() as client:
            request = client.build_request(
                method,
                url,
                json=json,  # using json for data to ensure it sends as application/json
                params=params,
                headers=headers,
                timeout=timeout,
            )

            response = await client.send(request)
            if response.status_code != 200:
                if error_handler:
                    return error_handler(response)
                else:
                    error_msg = f"Request to {url} failed, error: {response.text}"
                    raise Exception(error_msg)
            if success_handler:
                return success_handler(response)
            return response.json()

    async def _apply_to_worker_manager_instances(self):
        pass

    async def supported_models(self) -> List[WorkerSupportedModel]:
        worker_instances = await self.get_model_instances(
            WORKER_MANAGER_SERVICE_TYPE, WORKER_MANAGER_SERVICE_NAME
        )

        async def get_supported_models(worker_run_data) -> List[WorkerSupportedModel]:
            def handler(response):
                return list(WorkerSupportedModel.from_dict(m) for m in response.json())

            return await self._fetch_from_worker(
                worker_run_data, "/models/supports", success_handler=handler
            )

        models = []
        results = await asyncio.gather(
            *(get_supported_models(worker) for worker in worker_instances)
        )
        for res in results:
            models += res
        return models

    async def _get_worker_service_instance(
        self, host: str = None, port: int = None
    ) -> List[WorkerRunData]:
        worker_instances = await self.get_model_instances(
            WORKER_MANAGER_SERVICE_TYPE, WORKER_MANAGER_SERVICE_NAME
        )
        error_msg = "Cound not found worker instances"
        if host and port:
            worker_instances = [
                ins for ins in worker_instances if ins.host == host and ins.port == port
            ]
            error_msg = f"Cound not found worker instances for host {host} port {port}"
        if not worker_instances:
            raise Exception(error_msg)
        return worker_instances

    async def model_startup(self, startup_req: WorkerStartupRequest):
        worker_instances = await self._get_worker_service_instance(
            startup_req.host, startup_req.port
        )
        worker_run_data = worker_instances[0]
        logger.info(f"Start model remote, startup_req: {startup_req}")
        return await self._fetch_from_worker(
            worker_run_data,
            "/models/startup",
            method="POST",
            json=startup_req.dict(),
            success_handler=lambda x: None,
        )

    async def model_shutdown(self, shutdown_req: WorkerStartupRequest):
        worker_instances = await self._get_worker_service_instance(
            shutdown_req.host, shutdown_req.port
        )
        worker_run_data = worker_instances[0]
        logger.info(f"Shutdown model remote, shutdown_req: {shutdown_req}")
        return await self._fetch_from_worker(
            worker_run_data,
            "/models/shutdown",
            method="POST",
            json=shutdown_req.dict(),
            success_handler=lambda x: None,
        )

    def _build_worker_instances(
        self, model_name: str, instances: List[ModelInstance]
    ) -> List[WorkerRunData]:
        worker_instances = []
        for instance in instances:
            worker_instances.append(
                self._build_single_worker_instance(model_name, instance)
            )
        return worker_instances

    def _build_single_worker_instance(self, model_name: str, instance: ModelInstance):
        worker = RemoteModelWorker()
        worker.load_worker(model_name, host=instance.host, port=instance.port)
        wr = WorkerRunData(
            host=instance.host,
            port=instance.port,
            worker_type=worker.worker_type().value,
            worker_key=instance.model_name,
            worker=worker,
            worker_params=None,
            model_params=None,
            stop_event=asyncio.Event(),
            semaphore=asyncio.Semaphore(100),  # Not limit in client
        )
        return wr

    async def get_model_instances(
        self, worker_type: str, model_name: str, healthy_only: bool = True
    ) -> List[WorkerRunData]:
        worker_key = self._worker_key(worker_type, model_name)
        instances: List[ModelInstance] = await self.model_registry.get_all_instances(
            worker_key, healthy_only
        )
        return self._build_worker_instances(model_name, instances)

    async def get_all_model_instances(
        self, worker_type: str, healthy_only: bool = True
    ) -> List[WorkerRunData]:
        instances: List[
            ModelInstance
        ] = await self.model_registry.get_all_model_instances(healthy_only=healthy_only)
        result = []
        for instance in instances:
            name, wt = WorkerType.parse_worker_key(instance.model_name)
            if wt != worker_type:
                continue
            result.append(self._build_single_worker_instance(name, instance))
        return result

    def sync_get_model_instances(
        self, worker_type: str, model_name: str, healthy_only: bool = True
    ) -> List[WorkerRunData]:
        worker_key = self._worker_key(worker_type, model_name)
        instances: List[ModelInstance] = self.model_registry.sync_get_all_instances(
            worker_key, healthy_only
        )
        return self._build_worker_instances(model_name, instances)

    async def worker_apply(self, apply_req: WorkerApplyRequest) -> WorkerApplyOutput:
        async def _remote_apply_func(worker_run_data: WorkerRunData):
            return await self._fetch_from_worker(
                worker_run_data,
                "/apply",
                method="POST",
                json=apply_req.dict(),
                success_handler=lambda res: WorkerApplyOutput(**res.json()),
                error_handler=lambda res: WorkerApplyOutput(
                    message=res.text, success=False
                ),
            )

        results = await self._apply_worker(apply_req, _remote_apply_func)
        if results:
            return results[0]
