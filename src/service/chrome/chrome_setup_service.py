from enum import Enum
import os
import subprocess
from pathlib import Path
import asyncio
from typing import ClassVar
from loguru import logger
from py_spring_core import BeanCollection, Component, Properties
from pydantic import BaseModel
from pyhelm3 import Client


class SystemCommandTemplate(Enum):
    CHECK_NAMESPACE_EXISTS = "kubectl get namespace {namespace} --no-headers --ignore-not-found"
    GET_POD_IP = "kubectl get pods -n {namespace} -o yaml | grep 'podIP:' | awk '{{print $2}}'"
    GET_SERVICE_IP = "kubectl get svc -n {namespace} -o yaml | grep 'clusterIP:' | awk '{{print $2}}'"
    DELETE_NAMESPACE = "kubectl delete namespace {namespace} --wait=true"

class HelmProperties(Properties):
    __key__ = "helm"
    kube_config_path: str


class ChromeDeployment(BaseModel):
    namespace: str
    pod_ip: str
    service_ip: str


class HelmBeanCollection(BeanCollection):
    props: HelmProperties
    @classmethod
    def create_helm_client(cls) -> Client:
        return Client(kubeconfig = Path(cls.props.kube_config_path))

class ChomeSetupService(Component):
    client: Client
    release_name: ClassVar[str] = "chrome"
    properties: HelmProperties
    chart_path: ClassVar[str] = f"{os.getcwd()}/src/service/chrome/selenium"
    
    def install_chrome_chart(self, namespace: str) -> ChromeDeployment:
        # Install chart from local path
        chart = asyncio.run(self.client.get_chart(chart_ref = self.chart_path))
        asyncio.run(self.client.install_or_upgrade_release(
            release_name = self.release_name,
            chart = chart,
            create_namespace = True,
            namespace = namespace,
            wait = True
        ))
        logger.info(f"Installed chart {self.release_name} in namespace {namespace}")
        deployment = self.get_chrome_deployment(namespace = namespace)
        return deployment

    def uninstall_chrome_chart(self, namespace: str) -> None:
        asyncio.run(self.client.uninstall_release(
            release_name = self.release_name,
            namespace = namespace,
            wait = True
        ))
        logger.info(f"Uninstalled chart {self.release_name} in namespace {namespace}")
        self.delete_namespace(namespace = namespace)
        
    
    def get_chrome_deployment(self, namespace: str) -> ChromeDeployment:
        # Get pod IP
        pod_cmd = SystemCommandTemplate.GET_POD_IP.value.format(namespace = namespace)
        pod_ip = subprocess.check_output(
            pod_cmd, 
            shell=True, 
            env={"KUBECONFIG": self.properties.kube_config_path, **os.environ},
            text=True
        ).strip()
        
        # Get service IP
        svc_cmd = SystemCommandTemplate.GET_SERVICE_IP.value.format(namespace = namespace)
        service_ip = subprocess.check_output(
            svc_cmd, 
            shell=True, 
            env={"KUBECONFIG": self.properties.kube_config_path, **os.environ},
            text=True
        ).strip()
        
        return ChromeDeployment(namespace=namespace, pod_ip=pod_ip, service_ip=service_ip)
    
    def is_namespace_exists(self, namespace: str) -> bool:
        cmd = SystemCommandTemplate.CHECK_NAMESPACE_EXISTS.value.format(namespace = namespace)
        output = subprocess.run(
            cmd, 
            shell=True, 
            env={"KUBECONFIG": self.properties.kube_config_path, **os.environ},
            check=True
        ).stdout
        if output is None:
            return False
        return "Active" in output.decode("utf-8")
    
    def delete_namespace(self, namespace: str) -> None:
        if not self.is_namespace_exists(namespace):
            logger.warning(f"Namespace {namespace} not found")
            return
        subprocess.run(
            SystemCommandTemplate.DELETE_NAMESPACE.value.format(namespace = namespace),
            shell=True,
            env={"KUBECONFIG": self.properties.kube_config_path, **os.environ},
            check=True
        )
        logger.info(f"Deleted namespace {namespace}")