#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2026/10/22 13:00
@Author  : weiyutao
@File    : job_manager.py

任务编排：登记流水线后台任务、线程执行、进度与状态查询。
"""
from __future__ import annotations

import logging
import threading
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

from curve_pipeline import run_pipeline


class JobManager:
    """流水线后台任务管理器：提交、执行、状态查询。"""

    def __init__(self, outputs_root: str):
        """初始化任务管理器。

        Args:
            outputs_root (str): 任务默认输出根目录。
        """
        self.logger = logging.getLogger('JobManager')
        self.outputs_root = outputs_root
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()

    def submit(self, hainan_dir: str) -> str:
        """提交一个流水线任务并在后台线程执行。

        Args:
            hainan_dir (str): hainan 数据目录。

        Returns:
            str: 任务ID。
        """
        hainan = Path(hainan_dir).expanduser()
        if not hainan.is_dir():
            raise ValueError(f'[JobManager]-提交任务- hainan目录不存在：{hainan}')
        for stem in ('wind', 'solar'):
            if not (hainan / stem).is_dir() and not (hainan / f'{stem}.nc').is_file():
                raise ValueError(f'[JobManager]-提交任务- {hainan} 下缺少 {stem} 文件夹或 {stem}.nc')
        job_id = uuid.uuid4().hex[:12]
        with self._lock:
            self._jobs[job_id] = {'status': 'running', 'progress': 0.0,
                                  'detailed_status': '已提交', 'error_message': '',
                                  'created_at': datetime.now(timezone.utc).isoformat()}
        thread = threading.Thread(target=self._run, args=(job_id, hainan_dir), daemon=True)
        with self._lock:
            self._jobs[job_id]['thread'] = thread
        thread.start()
        self.logger.info('提交任务 %s hainan=%s', job_id, hainan_dir)
        return job_id

    def status(self, job_id: str) -> dict:
        """查询任务状态。

        Args:
            job_id (str): 任务ID。

        Returns:
            dict: {status, progress, detailed_status, error_message}。

        Raises:
            LookupError: 任务不存在。
        """
        with self._lock:
            if job_id not in self._jobs:
                raise LookupError(f'未找到任务 {job_id}')
            job = self._jobs[job_id]
            return {'status': job['status'], 'progress': job['progress'],
                    'detailed_status': job['detailed_status'],
                    'error_message': job['error_message']}

    def _progress_hook(self, job_id: str, step: int, text: str):
        """记录任务进度（步骤0-6 映射为 0~1）。"""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job['progress'] = round(min(max(step / 6.0, 0.0), 1.0), 4)
                job['detailed_status'] = text

    def _run(self, job_id: str, hainan_dir: str):
        """后台线程执行流水线并回写状态。"""
        try:
            result = run_pipeline(
                {'hainan_dir': hainan_dir, 'out_dir': self.outputs_root},
                progress=lambda step, text: self._progress_hook(job_id, step, text))
            with self._lock:
                job = self._jobs[job_id]
                job.update({'status': 'succeeded', 'progress': 1.0,
                            'detailed_status': f"完成，复核通过={result['复核结果']['通过']}"})
            self.logger.info('任务 %s 完成', job_id)
        except ValueError as exc:
            self.logger.warning('[任务]-%s- 参数或数据错误: %s', job_id, exc)
            with self._lock:
                job = self._jobs[job_id]
                job.update({'status': 'failed', 'detailed_status': '失败',
                            'error_message': f'[任务]-{job_id}- 运行流水线: {exc}'})
        except Exception as exc:
            self.logger.error('[任务]-%s- 运行异常: %s\n%s', job_id, exc, traceback.format_exc())
            with self._lock:
                job = self._jobs[job_id]
                job.update({'status': 'failed', 'detailed_status': '失败',
                            'error_message': f'[任务]-{job_id}- 运行流水线: {type(exc).__name__}: {exc}'})
