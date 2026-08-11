# -*- coding: utf-8 -*-
"""
UI Flow 执行器 - 将 UI Flow JSON 转换为 Airtest 动作并执行
"""
import os
import time
import logging
import json
import re
import copy
from typing import Any, Dict, List, Optional
from django.conf import settings

from airtest.core.api import (
    Template,
    wait,
    touch,
    sleep,
    swipe,
    snapshot,
    exists,
    double_click,
    G,
    ST,
    text as airtest_text,
)

# 导入 OCR 工具
try:
    from ..utils.ocr_helper import get_ocr_helper
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

try:
    import allure
    ALLURE_AVAILABLE = True
except ImportError:
    ALLURE_AVAILABLE = False

logger = logging.getLogger(__name__)


class UiFlowRunner:
    """将 ui_flow 转换为 Airtest 动作并执行"""
    
    def __init__(self, image_base_dir: Optional[str] = None, username: Optional[str] = None):
        """
        初始化 UiFlowRunner
        
        Args:
            image_base_dir: 图片元素基础目录
            username: 执行用户名，用于截图目录分组
        """
        if image_base_dir:
            self.image_base_dir = image_base_dir
        else:
            # 使用统一的 Template 目录作为图片基础目录
            self.image_base_dir = os.path.join(settings.BASE_DIR, 'apps', 'app_automation', 'Template')
        
        # 截图保存目录: media/app-automation/screenshots/{username}/
        self.screenshots_dir = os.path.join(
            settings.MEDIA_ROOT, 'app-automation', 'screenshots', username or 'unknown'
        )
        
        os.makedirs(self.image_base_dir, exist_ok=True)
        os.makedirs(self.screenshots_dir, exist_ok=True)
        
        # 上下文变量
        self.context: Dict[str, Any] = {
            'global': {},
            'local': {},
            'outputs': {},
        }
        
        # 运行时配置
        self.runtime: Dict[str, Any] = {
            'retry_times': 3,
            'retry_interval': 0.5,
        }
        
        # OCR 工具（延迟初始化）
        self._ocr_helper = None
        
        logger.info(f"初始化UiFlowRunner，图片目录: {self.image_base_dir}")
    
    def run(
        self,
        ui_flow: List[Dict[str, Any]],
        variables: Optional[List[Dict[str, Any]]] = None,
        runtime: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        执行 UI Flow
        
        Args:
            ui_flow: UI Flow 配置列表
            variables: 变量列表
            runtime: 运行时配置
            progress_callback: 进度回调函数，签名为 callback(current_step, total_steps, step_name, status)
                其中 status 为 'running' | 'passed' | 'failed'
            
        Returns:
            执行结果字典
        """
        if isinstance(ui_flow, dict):
            ui_flow = ui_flow.get('steps') or []
        if not isinstance(ui_flow, list):
            raise ValueError("ui_flow 必须是列表")
        
        # 初始化上下文
        self._init_context(variables, runtime)
        
        # 执行所有步骤
        total_steps = len(ui_flow)
        passed_steps = 0
        failed_steps = 0
        
        logger.info(f"开始执行 UI Flow，共 {total_steps} 个步骤")
        
        for idx, step in enumerate(ui_flow, 1):
            step_name = step.get('name', step.get('type', 'unknown'))
            
            # 通知：步骤开始执行
            if progress_callback:
                try:
                    progress_callback(idx, total_steps, step_name, 'running')
                except Exception as cb_err:
                    logger.debug(f"进度回调失败: {cb_err}")
            
            try:
                logger.info(f"执行步骤 {idx}/{total_steps}: {step_name}")
                step_title = f"步骤{idx}-{step_name}"
                if ALLURE_AVAILABLE:
                    with allure.step(step_title):
                        self._execute_step(step)
                else:
                    self._execute_step(step)
                passed_steps += 1
                
                # 通知：步骤执行成功
                if progress_callback:
                    try:
                        progress_callback(idx, total_steps, step_name, 'passed')
                    except Exception as cb_err:
                        logger.debug(f"进度回调失败: {cb_err}")
                        
            except Exception as e:
                logger.error(f"步骤 {idx} 执行失败: {str(e)}", exc_info=True)
                failed_steps += 1
                self._attach_allure(f"步骤{idx}-{step.get('name', step.get('type', 'unknown'))}-error", step)
                
                # 通知：步骤执行失败
                if progress_callback:
                    try:
                        progress_callback(idx, total_steps, step_name, 'failed')
                    except Exception as cb_err:
                        logger.debug(f"进度回调失败: {cb_err}")
                
                # 如果配置了失败即停止，则抛出异常
                if runtime and runtime.get('stop_on_error', False):
                    raise
        
        logger.info(f"UI Flow 执行完成，通过: {passed_steps}，失败: {failed_steps}")
        
        return {
            'total': total_steps,
            'passed': passed_steps,
            'failed': failed_steps,
            'outputs': self.context.get('outputs', {}),
        }
    
    def _init_context(self, variables: Optional[List[Dict[str, Any]]] = None, runtime: Optional[Dict[str, Any]] = None):
        """初始化上下文"""
        self.context = {
            'global': {},
            'local': {},
            'outputs': {},
        }
        
        if runtime:
            self.runtime.update(runtime)
        
        if variables:
            self._load_variables(variables)
    
    def _load_variables(self, variables: List[Dict[str, Any]]):
        """加载变量到上下文"""
        for item in variables:
            if not isinstance(item, dict):
                continue
            
            name = item.get('name')
            if not name:
                continue
            
            scope = str(item.get('scope', 'local')).lower()
            value = item.get('value')
            
            self._set_variable(name, value, scope)
    
    def _set_variable(self, name: str, value: Any, scope: str = 'local'):
        """设置变量"""
        if scope not in self.context:
            scope = 'local'
        self.context[scope][name] = value
    
    def _get_variable(self, name: str, scope: Optional[str] = None) -> Any:
        """获取变量"""
        if scope:
            return self.context.get(scope, {}).get(name)
        
        # 按优先级查找：local -> global -> outputs
        for s in ['local', 'global', 'outputs']:
            if name in self.context.get(s, {}):
                return self.context[s][name]
        
        return None
    
    def _render_value(self, value: Any) -> Any:
        """渲染变量值"""
        if isinstance(value, str):
            # 支持 {{variable}} 和 ${variable} 语法
            pattern = re.compile(r'\{\{\s*([^}]+)\s*\}\}|\$\{\s*([^}]+)\s*\}')
            
            def replace_var(match):
                var_name = match.group(1) or match.group(2)
                var_value = self._get_variable(var_name.strip())
                return str(var_value) if var_value is not None else ''
            
            return pattern.sub(replace_var, value)
        
        elif isinstance(value, dict):
            return {k: self._render_value(v) for k, v in value.items()}
        
        elif isinstance(value, list):
            return [self._render_value(item) for item in value]
        
        return value
    
    def _execute_step(self, step: Dict[str, Any]):
        """执行单个步骤，支持基础组件和自定义组件"""
        # 使用 type 字段获取步骤类型（兼容旧录制格式的 action）
        action_type = step.get('type') or step.get('action') or ''
        action = action_type.lower() if action_type else ''
        if action == 'tap':
            action = 'click'
        
        # 渲染步骤参数
        step = self._render_value(step)
        
        # 将 config 中的字段合并到顶层，便于各动作方法直接读取
        # 前端保存的数据结构为 { type, name, config: { selector_type, selector, ... } }
        config = step.get('config')
        if isinstance(config, dict):
            for key, value in config.items():
                if key not in step:
                    step[key] = value

        # 兼容旧录制：input 用 text 而非 value
        if action == 'input' and not step.get('value') and step.get('text') is not None:
            step['value'] = step['text']
        
        # ---- 步骤级重试机制 ----
        retry_times = int(step.get('retry_times', 0))
        retry_interval = float(step.get('retry_interval', self.runtime.get('retry_interval', 0.5)))
        
        if retry_times > 0:
            last_error = None
            for attempt in range(1 + retry_times):
                try:
                    self._dispatch_step(step, action)
                    return  # 成功则直接返回
                except Exception as e:
                    last_error = e
                    if attempt < retry_times:
                        logger.warning(
                            f"步骤 '{step.get('name', action)}' 第 {attempt + 1} 次失败，"
                            f"{retry_interval}s 后重试 (剩余 {retry_times - attempt - 1} 次): {e}"
                        )
                        sleep(retry_interval)
            raise last_error
        else:
            self._dispatch_step(step, action)
    
    def _dispatch_step(self, step: Dict[str, Any], action: str):
        """分发步骤到对应的 handler（基础组件）或展开执行（自定义组件）"""
        
        # 自定义组件展开执行
        if step.get('kind') == 'custom':
            self._execute_custom_component(step)
            return
        
        # 根据动作类型执行
        action_map = {
            # 基础动作
            'click': self._action_click,
            'touch': self._action_click,
            'input': self._action_input,
            'swipe': self._action_swipe,
            'double_click': self._action_double_click,
            'long_press': self._action_long_press,
            'drag': self._action_drag,
            'swipe_to': self._action_swipe_to,
            
            # 条件动作
            'image_exists_click': self._action_image_exists_click,
            'image_exists_click_chain': self._action_image_exists_click_chain,
            
            # 工具类
            'set_variable': self._action_set_variable,
            'unset_variable': self._action_unset_variable,
            'extract_output': self._action_extract_output,
            'screenshot': self._action_screenshot,
            'api_request': self._action_api_request,
            
            # 控制流
            'wait': self._action_wait,
            'sleep': self._action_wait,
            'if': self._action_if,
            'loop': self._action_loop,
            'sequence': self._action_sequence,
            'try': self._action_try,
            
            # 断言
            'assert': self._action_assert,
            'foreach_assert': self._action_foreach_assert,
        }
        
        handler = action_map.get(action)
        if handler:
            handler(step)
        else:
            # action_map 中找不到，尝试作为自定义组件查找
            if self._try_execute_as_custom(step, action):
                return
            logger.warning(f"未知的动作类型: {action} (步骤: {step.get('name', 'unknown')})")

    # ---------- 自定义组件展开 ----------

    def _load_custom_component_defs(self) -> Dict[str, Any]:
        """从数据库加载所有启用的自定义组件定义，缓存到实例上"""
        if not hasattr(self, '_custom_defs_cache'):
            try:
                from ..models import AppCustomComponent
                defs = {}
                for comp in AppCustomComponent.objects.filter(enabled=True):
                    defs[comp.type] = {
                        'name': comp.name,
                        'steps': comp.steps or [],
                        'schema': comp.schema or {},
                        'default_config': comp.default_config or {},
                    }
                self._custom_defs_cache = defs
                logger.debug(f"已加载 {len(defs)} 个自定义组件定义")
            except Exception as e:
                logger.warning(f"加载自定义组件定义失败: {e}")
                self._custom_defs_cache = {}
        return self._custom_defs_cache

    def _execute_custom_component(self, step: Dict[str, Any]):
        """
        展开并执行自定义组件。
        自定义组件的 steps 是基础组件步骤列表，逐个执行。
        步骤中的参数可通过 config 覆盖默认值。
        """
        comp_type = step.get('type', '')
        comp_name = step.get('name', comp_type)
        
        # 优先从步骤自带的 steps 字段获取（前端可能直接带了）
        sub_steps = step.get('steps')
        
        if not sub_steps:
            # 从数据库加载
            defs = self._load_custom_component_defs()
            comp_def = defs.get(comp_type)
            if not comp_def:
                raise ValueError(f"自定义组件 '{comp_type}' 未找到，请检查是否已创建并启用")
            sub_steps = comp_def.get('steps', [])
        
        if not sub_steps or not isinstance(sub_steps, list):
            logger.warning(f"自定义组件 '{comp_name}' 没有步骤，跳过")
            return
        
        # 深拷贝，避免修改原始定义
        sub_steps = copy.deepcopy(sub_steps)
        
        # 将自定义组件的 config 参数注入到子步骤中（作为变量可渲染）
        comp_config = step.get('config', {})
        if isinstance(comp_config, dict):
            for key, value in comp_config.items():
                if key not in ('type', 'name', 'kind', 'steps'):
                    self._set_variable(key, value, 'local')
        
        logger.info(f"展开自定义组件 '{comp_name}' ({comp_type})，共 {len(sub_steps)} 个子步骤")
        
        for sub_idx, sub_step in enumerate(sub_steps, 1):
            sub_name = sub_step.get('name', sub_step.get('type', 'unknown'))
            logger.info(f"  自定义组件子步骤 {sub_idx}/{len(sub_steps)}: {sub_name}")
            self._execute_step(sub_step)

    def _try_execute_as_custom(self, step: Dict[str, Any], action: str) -> bool:
        """尝试将未知的 action_type 作为自定义组件执行，成功返回 True"""
        defs = self._load_custom_component_defs()
        if action in defs:
            step['kind'] = 'custom'
            self._execute_custom_component(step)
            return True
        return False

    def _safe_filename(self, text: str) -> str:
        safe = re.sub(r'[^0-9a-zA-Z_\-]+', '_', str(text))
        return safe.strip('_') or "step"

    def _capture_screenshot(self, name_prefix: str) -> Optional[str]:
        try:
            filename = f"{self._safe_filename(name_prefix)}_{int(time.time())}.png"
            full_path = os.path.join(self.screenshots_dir, filename)
            result = snapshot(filename=full_path)
            if isinstance(result, dict):
                path = result.get("screen")
                if path and os.path.exists(path):
                    return path
            if os.path.exists(full_path):
                return full_path
        except Exception:
            logger.exception("截图失败")
        return None

    def _attach_allure(self, name: str, step: Optional[Dict[str, Any]] = None) -> None:
        if not ALLURE_AVAILABLE:
            return
        if step is not None:
            try:
                allure.attach(
                    json.dumps(step, ensure_ascii=False, indent=2),
                    name=f"{name}-step",
                    attachment_type=allure.attachment_type.JSON
                )
            except Exception:
                logger.exception("Allure JSON 附件写入失败")
        path = self._capture_screenshot(name)
        if path:
            try:
                allure.attach.file(path, name=name, attachment_type=allure.attachment_type.PNG)
            except Exception:
                logger.exception("Allure 截图附件写入失败: %s", path)
    
    def _resolve_selector(self, step: Dict[str, Any]) -> Any:
        """
        解析选择器
        
        支持的类型:
        - element_id: 从数据库加载元素
        - image: 图片元素
        - pos: 坐标点
        - region: 区域
        """
        # 优先使用 element_id；若步骤带有 fallback_pos，失败时由 _action_touch 回退
        element_id = step.get('element_id')
        if element_id:
            return self._resolve_element_by_id(element_id)
        
        selector_type = step.get('selector_type', 'image')
        selector = step.get('selector', '')
        
        if selector_type == 'image':
            # 图片选择器
            if not selector:
                logger.warning(f"图片选择器的 selector 为空，请检查步骤配置: {step.get('name', step.get('type', 'unknown'))}")
                return None
            
            image_scope = step.get('image_scope', 'common')
            image_path = os.path.join(self.image_base_dir, image_scope, selector)
            
            if not os.path.isfile(image_path):
                logger.warning(f"图片文件不存在: {image_path}")
                return None
            
            threshold = step.get('image_threshold', 0.7)
            if str(image_scope) == 'recorded' or 'recorded' in str(image_path).replace('\\', '/'):
                threshold = min(float(threshold or 0.7), 0.55)
            return Template(image_path, threshold=threshold)
        
        elif selector_type == 'pos':
            # 坐标选择器
            if isinstance(selector, str):
                parts = [p.strip() for p in selector.split(',')]
                if len(parts) >= 2:
                    return (int(parts[0]), int(parts[1]))
            elif isinstance(selector, (list, tuple)) and len(selector) >= 2:
                return (int(selector[0]), int(selector[1]))
            
            logger.warning(f"无效的坐标格式: {selector}")
            return None
        
        elif selector_type == 'region':
            # 区域选择器（用于 exists 等）
            if isinstance(selector, str):
                parts = [p.strip() for p in selector.split(',')]
                if len(parts) >= 4:
                    return (int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3]))
            elif isinstance(selector, (list, tuple)) and len(selector) >= 4:
                return tuple(int(x) for x in selector[:4])
            
            logger.warning(f"无效的区域格式: {selector}")
            return None
        
        logger.warning(f"未知的选择器类型: {selector_type}")
        return None
    
    def _resolve_element_by_id(self, element_id: int) -> Any:
        """从数据库加载元素"""
        try:
            from apps.app_automation.models import AppElement
            
            element = AppElement.objects.filter(id=element_id, is_active=True).first()
            if not element:
                logger.warning(f"未找到元素: element_id={element_id}")
                return None
            
            # 记录使用次数
            element.increment_usage()
            
            # 根据元素类型返回选择器
            if element.element_type == 'image':
                image_rel_path = element.config.get('image_path', '')
                if not image_rel_path:
                    logger.warning(f"元素 {element_id} 的 image_path 为空")
                    return None
                
                image_path = os.path.join(self.image_base_dir, image_rel_path)
                
                if not os.path.isfile(image_path):
                    logger.warning(f"图片文件不存在: {image_path}")
                    return None
                
                threshold = element.config.get('image_threshold', element.config.get('threshold', 0.7))
                # 录制元素适当放宽阈值，提升回放成功率
                tags = getattr(element, 'tags', None) or []
                if 'recorded' in tags or str(image_rel_path).startswith('recorded/'):
                    threshold = min(float(threshold or 0.7), 0.55)
                return Template(image_path, threshold=threshold)
            
            elif element.element_type == 'pos':
                x = element.config.get('x')
                y = element.config.get('y')
                return (x, y)
            
            elif element.element_type == 'region':
                x1 = element.config.get('x1')
                y1 = element.config.get('y1')
                x2 = element.config.get('x2')
                y2 = element.config.get('y2')
                return (x1, y1, x2, y2)
            
        except Exception as e:
            logger.error(f"解析元素失败: element_id={element_id}, 错误: {e}", exc_info=True)
            return None
    
    def _action_touch(self, step: Dict[str, Any]):
        """点击动作：优先图片/元素匹配，失败则回退到录制坐标。"""
        from airtest.core.error import TargetNotFoundError

        target = self._resolve_selector(step)
        if target is None:
            step_name = step.get('name', step.get('type', 'unknown'))
            raise ValueError(f"步骤 '{step_name}' 无法解析选择器，请检查元素配置（selector 或 element_id）")

        fallback = self._extract_fallback_pos(step)
        try:
            logger.info(f"执行点击: {target}")
            # 录制图匹配给更短超时，失败后快速走坐标
            old_timeout = getattr(ST, 'FIND_TIMEOUT', 6)
            try:
                if not isinstance(target, tuple):
                    ST.FIND_TIMEOUT = min(float(old_timeout), float(step.get('timeout') or 4))
                touch(target)
            finally:
                ST.FIND_TIMEOUT = old_timeout
        except TargetNotFoundError as exc:
            if fallback:
                logger.warning(f"图片未匹配到，回退坐标点击 {fallback}: {exc}")
                touch(fallback)
            else:
                raise

    def _extract_fallback_pos(self, step: Dict[str, Any]) -> Optional[tuple]:
        """从步骤中提取坐标兜底（录制时写入的 fallback_pos / 原始 selector）。"""
        candidates = [
            step.get('fallback_pos'),
            step.get('pos'),
        ]
        selector = step.get('selector')
        selector_type = (step.get('selector_type') or '').lower()
        if selector_type == 'pos' or isinstance(selector, (list, tuple)):
            candidates.append(selector)
        # config 可能已合并到顶层；再看原始 config
        cfg = step.get('config') if isinstance(step.get('config'), dict) else {}
        candidates.extend([cfg.get('fallback_pos'), cfg.get('pos')])
        if (cfg.get('selector_type') or '').lower() == 'pos':
            candidates.append(cfg.get('selector'))

        for item in candidates:
            if item is None:
                continue
            if isinstance(item, str):
                parts = [p.strip() for p in item.replace('[', '').replace(']', '').split(',') if p.strip()]
                if len(parts) >= 2:
                    try:
                        return (int(float(parts[0])), int(float(parts[1])))
                    except ValueError:
                        continue
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                try:
                    return (int(item[0]), int(item[1]))
                except (TypeError, ValueError):
                    continue
        return None
    
    def _action_double_click(self, step: Dict[str, Any]):
        """双击动作"""
        target = self._resolve_selector(step)
        if target:
            logger.info(f"执行双击: {target}")
            double_click(target)
    
    def _action_swipe(self, step: Dict[str, Any]):
        """滑动动作"""
        import json
        
        start = step.get('start')
        end = step.get('end')
        duration = step.get('duration', 0.5)
        
        # 处理 pos 定位方式的 selector
        if not start and not end:
            selector = step.get('selector')
            selector_type = step.get('selector_type')
            if selector and selector_type == 'pos':
                try:
                    if isinstance(selector, str):
                        locator = json.loads(selector)
                    else:
                        locator = selector
                    if isinstance(locator, list) and len(locator) >= 2:
                        start = tuple(locator[0])
                        end = tuple(locator[1])
                    else:
                        raise ValueError(f"Invalid locator for swipe: {locator}")
                except (json.JSONDecodeError, ValueError) as e:
                    raise ValueError(f"Failed to parse swipe locator: {selector}, error: {e}")
        
        if isinstance(start, str):
            start = tuple(int(x) for x in start.split(','))
        if isinstance(end, str):
            end = tuple(int(x) for x in end.split(','))
        
        if not start or not end:
            raise ValueError(f"Missing start or end coordinates for swipe: start={start}, end={end}")
        
        logger.info(f"执行滑动: {start} -> {end}")
        swipe(start, end, duration=duration)
    
    def _action_wait(self, step: Dict[str, Any]):
        """等待：有 selector 时等待元素出现，没有时纯等待 timeout 秒"""
        target = self._resolve_selector(step)
        timeout = step.get('timeout', step.get('duration', 3))
        
        if target:
            logger.info(f"等待元素出现: {target}, 超时: {timeout}s")
            wait(target, timeout=timeout)
        else:
            logger.info(f"等待 {timeout} 秒")
            sleep(timeout)
    
    def _action_snapshot(self, step: Dict[str, Any]):
        """截图"""
        name = step.get('name', f'snapshot_{int(time.time())}')
        filename = f"{name}.png"
        
        filepath = os.path.join(self.screenshots_dir, filename)
        
        logger.info(f"截图保存: {filepath}")
        snapshot(filename=filepath)
    
    def _action_text(self, step: Dict[str, Any]):
        """输入文本"""
        text_value = step.get('text', '')
        logger.info(f"输入文本: {text_value}")
        airtest_text(text_value)
    
    def _action_set_variable(self, step: Dict[str, Any]):
        """设置变量"""
        name = step.get('name')
        value = step.get('value')
        scope = step.get('scope', 'local')
        
        if name:
            self._set_variable(name, value, scope)
            logger.info(f"设置变量: {scope}.{name} = {value}")
    
    def _action_assert(self, step: Dict[str, Any]):
        """
        断言入口，根据 assert_type 分发到具体实现。
        支持 timeout 参数：断言失败后在 timeout 秒内持续重试（适配页面加载延迟）。
        
        支持的 assert_type:
        - text:   OCR 识别文本，支持 exact/contains/regex 匹配
        - number: OCR 识别数字（自动去除逗号等格式符号），精确匹配
        - regex:  OCR 识别文本，用正则表达式匹配（text + match_mode=regex 的快捷方式）
        - range:  OCR 识别数字，判断是否在 [min, max] 范围内
        - exists: 判断图片元素是否存在于屏幕上
        - image:  在屏幕上查找期望图片是否存在（图片对比断言）
        """
        assert_type = step.get('assert_type', 'text')
        timeout = float(step.get('timeout', 0))
        retry_interval = float(step.get('retry_interval', 1))
        
        assert_map = {
            'text': self._assert_text,
            'number': self._assert_number,
            'regex': self._assert_regex,
            'range': self._assert_range,
            'exists': self._assert_exists,
            'image': self._assert_image,
        }
        
        handler = assert_map.get(assert_type)
        if not handler:
            raise ValueError(f"未知的断言类型: {assert_type}，支持: {', '.join(assert_map.keys())}")
        
        # 无超时：直接执行一次
        if timeout <= 0:
            handler(step)
            return
        
        # 有超时：在 timeout 秒内持续重试
        deadline = time.time() + timeout
        last_error = None
        attempt = 0
        while True:
            attempt += 1
            try:
                handler(step)
                if attempt > 1:
                    logger.info(f"断言在第 {attempt} 次尝试后通过")
                return  # 断言通过
            except (AssertionError, Exception) as e:
                last_error = e
                if time.time() >= deadline:
                    break
                remaining = deadline - time.time()
                wait_time = min(retry_interval, remaining)
                if wait_time > 0:
                    logger.debug(
                        f"断言未通过 (第 {attempt} 次)，{wait_time:.1f}s 后重试: {e}"
                    )
                    sleep(wait_time)
        
        raise last_error
    
    # ---------- 断言内部实现 ----------
    
    def _parse_ocr_region(self, step: Dict[str, Any]) -> tuple:
        """
        从步骤配置中解析 OCR 区域坐标 (x1, y1, x2, y2)。
        同时支持 selector 和 ocr_selector 字段名。
        """
        selector = step.get('ocr_selector') or step.get('selector')
        selector_type = step.get('ocr_selector_type') or step.get('selector_type', 'region')
        
        if not selector:
            raise ValueError("断言需要 selector 或 ocr_selector 参数来指定 OCR 区域")
        
        if selector_type != 'region':
            raise ValueError(f"OCR 断言仅支持 selector_type=region，当前: {selector_type}")
        
        if isinstance(selector, str):
            parts = [int(p.strip()) for p in selector.split(',')]
            if len(parts) != 4:
                raise ValueError(f"region 格式错误，需要 4 个值 (x1,y1,x2,y2): {selector}")
            return tuple(parts)
        elif isinstance(selector, (list, tuple)) and len(selector) >= 4:
            return tuple(int(x) for x in selector[:4])
        else:
            raise ValueError(f"无法解析 region: {selector}")
    
    def _ocr_recognize_text(self, region: tuple) -> str:
        """OCR 识别指定区域的文本"""
        ocr = self._get_ocr_helper()
        return ocr.recognize_region_text(region)
    
    def _ocr_recognize_number(self, region: tuple) -> int:
        """OCR 识别指定区域的数字（自动去除逗号等格式符号）"""
        ocr = self._get_ocr_helper()
        return ocr.recognize_region_number(region)
    
    def _assert_text(self, step: Dict[str, Any]):
        """文本断言：OCR 识别文本，支持 exact/contains/regex 匹配"""
        if not OCR_AVAILABLE:
            raise RuntimeError("文本断言需要 OCR 支持，请安装 easyocr")
        
        region = self._parse_ocr_region(step)
        expected = step.get('expected', '')
        match_mode = step.get('match_mode', 'contains')
        
        actual_text = self._ocr_recognize_text(region)
        
        if match_mode == 'exact':
            passed = actual_text == expected
        elif match_mode == 'contains':
            passed = expected in actual_text
        elif match_mode == 'regex':
            passed = re.search(expected, actual_text) is not None
        else:
            raise ValueError(f"不支持的 match_mode: {match_mode}")
        
        if not passed:
            raise AssertionError(f"文本断言失败: 期望 '{expected}' ({match_mode}), 实际 '{actual_text}'")
        
        logger.info(f"文本断言成功: '{expected}' ({match_mode}) 匹配 '{actual_text}'")
    
    def _assert_number(self, step: Dict[str, Any]):
        """数值断言：OCR 识别数字（去逗号），与期望值精确匹配"""
        if not OCR_AVAILABLE:
            raise RuntimeError("数值断言需要 OCR 支持，请安装 easyocr")
        
        region = self._parse_ocr_region(step)
        expected_raw = step.get('expected', '0')
        
        # 期望值也做去逗号处理，兼容用户填 "3,000,000" 或 "3000000"
        try:
            expected_num = int(str(expected_raw).replace(',', '').replace(' ', ''))
        except (ValueError, TypeError):
            raise ValueError(f"number 断言的期望值无法转为数字: {expected_raw}")
        
        actual_num = self._ocr_recognize_number(region)
        
        if actual_num != expected_num:
            raise AssertionError(f"数值断言失败: 期望 {expected_num}, 实际 {actual_num}")
        
        logger.info(f"数值断言成功: 期望 {expected_num}, 实际 {actual_num}")
    
    def _assert_regex(self, step: Dict[str, Any]):
        """正则断言：OCR 识别文本，用正则表达式匹配"""
        if not OCR_AVAILABLE:
            raise RuntimeError("正则断言需要 OCR 支持，请安装 easyocr")
        
        region = self._parse_ocr_region(step)
        pattern = step.get('expected', '')
        
        if not pattern:
            raise ValueError("regex 断言需要在 expected 字段填写正则表达式")
        
        actual_text = self._ocr_recognize_text(region)
        
        match = re.search(pattern, actual_text)
        if not match:
            raise AssertionError(f"正则断言失败: 模式 '{pattern}' 未匹配到文本 '{actual_text}'")
        
        logger.info(f"正则断言成功: 模式 '{pattern}' 匹配到 '{match.group()}' (全文: '{actual_text}')")
    
    def _assert_range(self, step: Dict[str, Any]):
        """范围断言：OCR 识别数字，判断是否在 [min, max] 范围内"""
        if not OCR_AVAILABLE:
            raise RuntimeError("范围断言需要 OCR 支持，请安装 easyocr")
        
        region = self._parse_ocr_region(step)
        
        min_val = step.get('min')
        max_val = step.get('max')
        
        if min_val is None and max_val is None:
            raise ValueError("range 断言需要至少设置 min 或 max 之一")
        
        # 转换为数值
        try:
            min_num = int(str(min_val).replace(',', '').replace(' ', '')) if min_val is not None else None
        except (ValueError, TypeError):
            raise ValueError(f"range 断言的 min 值无法转为数字: {min_val}")
        try:
            max_num = int(str(max_val).replace(',', '').replace(' ', '')) if max_val is not None else None
        except (ValueError, TypeError):
            raise ValueError(f"range 断言的 max 值无法转为数字: {max_val}")
        
        actual_num = self._ocr_recognize_number(region)
        
        if min_num is not None and actual_num < min_num:
            raise AssertionError(f"范围断言失败: 实际值 {actual_num} 小于最小值 {min_num}")
        if max_num is not None and actual_num > max_num:
            raise AssertionError(f"范围断言失败: 实际值 {actual_num} 大于最大值 {max_num}")
        
        range_desc = f"[{min_num if min_num is not None else '-∞'}, {max_num if max_num is not None else '+∞'}]"
        logger.info(f"范围断言成功: 实际值 {actual_num} 在范围 {range_desc} 内")
    
    def _assert_exists(self, step: Dict[str, Any]):
        """存在性断言：判断图片元素是否存在于屏幕上"""
        target = self._resolve_selector(step)
        expected_exists = step.get('expected_exists', True)
        
        result = exists(target) is not None
        
        if expected_exists and not result:
            raise AssertionError(f"期望元素存在，但实际不存在")
        elif not expected_exists and result:
            raise AssertionError(f"期望元素不存在，但实际存在")
        
        logger.info(f"存在性断言成功: 期望存在={expected_exists}, 实际存在={result}")
    
    def _assert_image(self, step: Dict[str, Any]):
        """图片断言：在屏幕上查找期望图片是否存在"""
        expected_image = step.get('expected', '')
        image_scope = step.get('expected_image_scope') or step.get('image_scope', 'common')
        threshold = step.get('image_threshold', 0.7)
        
        if not expected_image:
            raise ValueError("image 断言需要在 expected 字段填写图片文件名")
        
        image_path = os.path.join(self.image_base_dir, image_scope, expected_image)
        
        if not os.path.isfile(image_path):
            raise ValueError(f"期望图片文件不存在: {image_path}")
        
        target = Template(image_path, threshold=threshold)
        result = exists(target)
        
        if result is None:
            raise AssertionError(f"图片断言失败: 未在屏幕上找到图片 '{expected_image}' (阈值: {threshold})")
        
        logger.info(f"图片断言成功: 在屏幕上找到图片 '{expected_image}', 位置: {result}")
    
    # ============ 新增动作方法 ============
    
    def _action_click(self, step: Dict[str, Any]):
        """点击动作（重命名自 _action_touch）"""
        self._action_touch(step)
    
    def _action_input(self, step: Dict[str, Any]):
        """输入文本"""
        target = self._resolve_selector(step)
        value = step.get('value', '')
        
        # 解析变量表达式（如随机数函数）
        from apps.core.variable_resolver import resolve_variables
        value = resolve_variables(value)
        
        send_enter = step.get('send_enter', False)
        
        if target:
            touch(target)
            time.sleep(0.3)
        
        logger.info(f"输入文本: {value}")
        airtest_text(value)
        
        # 如果需要发送回车键（用于搜索）
        if send_enter:
            time.sleep(0.2)
            try:
                from airtest.core.api import keyevent
                keyevent("KEYCODE_ENTER")
                logger.info("发送回车键")
            except ImportError:
                # 如果没有keyevent，尝试发送换行符
                airtest_text('\n')
                logger.info("发送换行符模拟回车")
    
    def _action_long_press(self, step: Dict[str, Any]):
        """长按"""
        target = self._resolve_selector(step)
        duration = step.get('duration', 2)
        
        if target:
            logger.info(f"长按: {target}, 时长: {duration}秒")
            touch(target, duration=duration)
    
    def _action_drag(self, step: Dict[str, Any]):
        """拖拽：从起点拖拽到终点"""
        # 解析起点
        start_config = {
            'selector': step.get('start_selector'),
            'selector_type': step.get('start_selector_type', 'image'),
            'image_scope': step.get('image_scope', 'common')
        }
        start = self._resolve_selector(start_config)
        
        # 解析终点
        end_config = {
            'selector': step.get('end_selector'),
            'selector_type': step.get('end_selector_type', 'image'),
            'image_scope': step.get('image_scope', 'common')
        }
        end = self._resolve_selector(end_config)
        
        duration = step.get('duration', 0.8)
        
        if start and end:
            logger.info(f"拖拽: {start} -> {end}")
            swipe(start, end, duration=duration)
    
    def _action_swipe_to(self, step: Dict[str, Any]):
        """滑动直到目标元素出现"""
        target_config = {
            'selector': step.get('target_selector'),
            'selector_type': step.get('target_selector_type', 'image'),
            'image_scope': step.get('image_scope', 'common')
        }
        target = self._resolve_selector(target_config)
        
        direction = step.get('direction', 'up')
        max_swipes = step.get('max_swipes', 5)
        interval = step.get('interval', 0.5)
        
        for i in range(max_swipes):
            if exists(target):
                logger.info(f"找到目标元素，停止滑动")
                return
            
            logger.info(f"第 {i+1}/{max_swipes} 次滑动: {direction}")
            swipe_vector = G.DEVICE.get_current_resolution()
            
            if direction == 'up':
                swipe((swipe_vector[0]//2, swipe_vector[1]*0.7), 
                      (swipe_vector[0]//2, swipe_vector[1]*0.3))
            elif direction == 'down':
                swipe((swipe_vector[0]//2, swipe_vector[1]*0.3), 
                      (swipe_vector[0]//2, swipe_vector[1]*0.7))
            elif direction == 'left':
                swipe((swipe_vector[0]*0.7, swipe_vector[1]//2), 
                      (swipe_vector[0]*0.3, swipe_vector[1]//2))
            elif direction == 'right':
                swipe((swipe_vector[0]*0.3, swipe_vector[1]//2), 
                      (swipe_vector[0]*0.7, swipe_vector[1]//2))
            
            time.sleep(interval)
        
        logger.warning(f"滑动 {max_swipes} 次后仍未找到目标元素")
    
    def _action_image_exists_click(self, step: Dict[str, Any]):
        """主定位存在则点击主定位，否则点击备用定位"""
        # 主定位
        main_config = {
            'selector': step.get('selector'),
            'selector_type': step.get('selector_type', 'image'),
            'image_scope': step.get('image_scope', 'common'),
            'image_threshold': step.get('image_threshold', 0.7)
        }
        main_target = self._resolve_selector(main_config)
        
        # 备用定位
        fallback_config = {
            'selector': step.get('fallback_selector'),
            'selector_type': step.get('fallback_selector_type', 'image'),
            'image_scope': step.get('fallback_image_scope', 'common'),
            'image_threshold': step.get('fallback_image_threshold', 0.7)
        }
        fallback_target = self._resolve_selector(fallback_config)
        
        if main_target and exists(main_target):
            logger.info(f"主定位存在，点击主定位")
            touch(main_target)
        elif fallback_target:
            logger.info(f"主定位不存在，点击备用定位")
            touch(fallback_target)
    
    def _action_image_exists_click_chain(self, step: Dict[str, Any]):
        """主定位存在则依次点击主定位和备用定位，否则只点击备用定位"""
        # 主定位
        main_config = {
            'selector': step.get('selector'),
            'selector_type': step.get('selector_type', 'image'),
            'image_scope': step.get('image_scope', 'common')
        }
        main_target = self._resolve_selector(main_config)
        
        # 备用定位
        fallback_config = {
            'selector': step.get('fallback_selector'),
            'selector_type': step.get('fallback_selector_type', 'image'),
            'image_scope': step.get('fallback_image_scope', 'common')
        }
        fallback_target = self._resolve_selector(fallback_config)
        
        if main_target and exists(main_target):
            logger.info(f"主定位存在，依次点击主定位和备用定位")
            touch(main_target)
            time.sleep(0.5)
        
        if fallback_target:
            touch(fallback_target)
    
    def _action_unset_variable(self, step: Dict[str, Any]):
        """删除变量"""
        name = step.get('name')
        scope = step.get('scope', 'local')
        
        if name and scope in self.context and name in self.context[scope]:
            del self.context[scope][name]
            logger.info(f"删除变量: {scope}.{name}")
    
    def _action_extract_output(self, step: Dict[str, Any]):
        """
        从变量中按路径提取字段并保存为新变量。
        
        配置示例:
            source: "local.response"      # 来源变量，格式: scope.var_name
            path: "body.data.token"       # 提取路径，支持多级 key 和列表索引 [0]
            name: "token"                 # 保存为新变量名
            scope: "local"                # 保存到哪个作用域
        """
        source = step.get('source', '')
        path = step.get('path', '')
        name = step.get('name')
        scope = step.get('scope', 'local')
        
        if not name:
            raise ValueError("extract_output 需要 name 参数（保存的变量名）")
        if not source:
            raise ValueError("extract_output 需要 source 参数（来源变量）")
        
        # 解析 source: "scope.var_name" 或直接 "var_name"
        source_value = self._get_variable(source)
        if source_value is None:
            # 尝试按 scope.name 格式解析
            parts = source.split('.', 1)
            if len(parts) == 2 and parts[0] in self.context:
                source_value = self.context[parts[0]].get(parts[1])
        
        if source_value is None:
            raise ValueError(f"来源变量不存在: {source}")
        
        # 按 path 逐级提取
        if path:
            current = source_value
            for key in self._parse_path(path):
                if isinstance(current, dict):
                    current = current.get(key)
                elif isinstance(current, (list, tuple)):
                    try:
                        current = current[int(key)]
                    except (ValueError, IndexError):
                        current = None
                else:
                    current = None
                
                if current is None:
                    raise ValueError(f"提取失败: 路径 '{path}' 在 '{key}' 处找不到值")
            
            extracted = current
        else:
            extracted = source_value
        
        self._set_variable(name, extracted, scope)
        logger.info(f"提取成功: {source}.{path} -> {scope}.{name} = {extracted}")
    
    @staticmethod
    def _parse_path(path: str) -> List[str]:
        """解析提取路径，支持 'a.b.c' 和 'a[0].b' 格式"""
        keys = []
        for part in path.split('.'):
            if '[' in part:
                # 处理 "items[0]" -> ["items", "0"]
                base, rest = part.split('[', 1)
                if base:
                    keys.append(base)
                for idx_part in rest.split('['):
                    idx_part = idx_part.rstrip(']')
                    if idx_part:
                        keys.append(idx_part)
            else:
                if part:
                    keys.append(part)
        return keys
    
    def _action_screenshot(self, step: Dict[str, Any]):
        """截图（重命名自 _action_snapshot）"""
        self._action_snapshot(step)
    
    def _action_api_request(self, step: Dict[str, Any]):
        """
        执行HTTP请求，支持状态码校验、自动/手动响应解析和字段提取。
        
        配置项:
            method: GET / POST / PUT / DELETE / PATCH
            url: 请求地址（支持变量渲染）
            headers / params / json / data: 请求参数
            timeout: 超时秒数，默认10
            response_type: auto(自动判断) / json / text / binary
            expected_status: 期望的 HTTP 状态码，如 200
            save_as: 将完整响应结果保存为变量名
            scope: 变量保存的作用域，默认 local
            extracts: 字段提取列表
                - path: "body.data.token"
                  name: "token"
                  scope: "local"
        """
        import requests as req_lib
        
        method = step.get('method', 'GET').upper()
        url = self._render_value(step.get('url', ''))
        headers = step.get('headers', {})
        params = step.get('params', {})
        json_data = step.get('json', {})
        data = step.get('data', {})
        timeout = step.get('timeout', 10)
        save_as = step.get('save_as', '')
        scope = step.get('scope', 'local')
        response_type = step.get('response_type', 'auto')
        expected_status = step.get('expected_status')
        extracts = step.get('extracts', [])
        
        if not url:
            raise ValueError("api_request 缺少 url 参数")
        
        # 渲染 headers/params 中的变量
        if isinstance(headers, dict):
            headers = {k: self._render_value(v) if isinstance(v, str) else v
                       for k, v in headers.items()}
        if isinstance(params, dict):
            params = {k: self._render_value(v) if isinstance(v, str) else v
                      for k, v in params.items()}
        
        logger.info(f"HTTP请求: {method} {url}")
        
        try:
            response = req_lib.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_data if json_data else None,
                data=data if data else None,
                timeout=timeout
            )
        except Exception as e:
            logger.error(f"HTTP请求失败: {str(e)}")
            raise
        
        # 解析响应体
        body = self._parse_response_body(response, response_type)
        
        result = {
            'status_code': response.status_code,
            'headers': dict(response.headers),
            'body': body
        }
        
        logger.info(f"HTTP响应: {response.status_code}")
        
        # 状态码校验
        if expected_status is not None:
            expected_status = int(expected_status)
            if response.status_code != expected_status:
                raise AssertionError(
                    f"HTTP状态码断言失败: 期望 {expected_status}, "
                    f"实际 {response.status_code}"
                )
        
        # 保存完整结果
        if save_as:
            self._set_variable(save_as, result, scope)
        
        # 字段提取
        if extracts and isinstance(extracts, list):
            for extract in extracts:
                if not isinstance(extract, dict):
                    continue
                e_path = extract.get('path', '')
                e_name = extract.get('name', '')
                e_scope = extract.get('scope', scope)
                if not e_name:
                    logger.warning(f"extracts 配置缺少 name，跳过: {extract}")
                    continue
                
                # 从 result 中按路径提取
                current = result
                try:
                    for key in self._parse_path(e_path):
                        if isinstance(current, dict):
                            current = current[key]
                        elif isinstance(current, (list, tuple)):
                            current = current[int(key)]
                        else:
                            raise KeyError(key)
                except (KeyError, IndexError, ValueError, TypeError) as e:
                    raise ValueError(
                        f"api_request extracts 提取失败: path='{e_path}' "
                        f"在 '{key}' 处出错: {e}"
                    )
                self._set_variable(e_name, current, e_scope)
                logger.info(f"api_request 提取: {e_path} -> {e_scope}.{e_name} = {current}")
    
    @staticmethod
    def _parse_response_body(response, response_type: str = 'auto'):
        """根据 response_type 解析响应体"""
        if response_type == 'json':
            try:
                return response.json()
            except Exception:
                return response.text
        elif response_type == 'text':
            return response.text
        elif response_type == 'binary':
            import base64
            return base64.b64encode(response.content).decode('ascii')
        else:
            # auto: 根据 Content-Type 自动判断
            content_type = response.headers.get('Content-Type', '')
            if 'json' in content_type or 'javascript' in content_type:
                try:
                    return response.json()
                except Exception:
                    return response.text
            return response.text
    
    def _action_if(self, step: Dict[str, Any]):
        """条件分支，支持丰富的操作符"""
        left = self._render_value(step.get('left', ''))
        right = self._render_value(step.get('right', ''))
        operator = step.get('operator', '==')
        then_steps = step.get('then_steps', [])
        else_steps = step.get('else_steps', [])
        
        condition = self._eval_condition(left, operator, right)
        
        logger.info(f"条件判断: {left} {operator} {right} = {condition}")
        
        # 执行分支
        if condition:
            for sub_step in then_steps:
                self._execute_step(sub_step)
        else:
            for sub_step in else_steps:
                self._execute_step(sub_step)
    
    @staticmethod
    def _eval_condition(left, operator: str, right) -> bool:
        """
        评估条件表达式。
        
        支持的操作符:
            ==, !=, >, >=, <, <=,
            in, not in, not_in,
            contains, notcontains, not_contains,
            regex, match,
            truthy, exists,
            falsy, not_exists,
            startswith, endswith
        """
        op = operator.strip().lower()
        
        # 相等判断
        if op == '==':
            return str(left) == str(right)
        if op == '!=':
            return str(left) != str(right)
        
        # 数值比较
        if op in ('>', '>=', '<', '<='):
            try:
                l_val, r_val = float(left), float(right)
            except (ValueError, TypeError):
                return False
            if op == '>':
                return l_val > r_val
            if op == '>=':
                return l_val >= r_val
            if op == '<':
                return l_val < r_val
            return l_val <= r_val
        
        # 包含判断
        if op == 'in':
            return str(left) in str(right)
        if op in ('not in', 'not_in'):
            return str(left) not in str(right)
        if op == 'contains':
            return str(right) in str(left)
        if op in ('notcontains', 'not_contains'):
            return str(right) not in str(left)
        
        # 正则匹配
        if op in ('regex', 'match'):
            try:
                return bool(re.search(str(right), str(left)))
            except re.error:
                return False
        
        # 真值 / 假值
        if op in ('truthy', 'exists'):
            return bool(left)
        if op in ('falsy', 'not_exists'):
            return not bool(left)
        
        # 前缀 / 后缀
        if op == 'startswith':
            return str(left).startswith(str(right))
        if op == 'endswith':
            return str(left).endswith(str(right))
        
        logger.warning(f"未知的条件操作符: {operator}，默认返回 False")
        return False
    
    def _action_loop(self, step: Dict[str, Any]):
        """循环：支持计数/条件/遍历三种模式"""
        mode = step.get('mode', 'count')
        steps = step.get('steps', [])
        max_loops = step.get('max_loops', 10)
        interval = step.get('interval', 0)
        
        if mode == 'count':
            # 计数循环
            times = step.get('times', 1)
            logger.info(f"计数循环: {times} 次")
            for i in range(times):
                logger.info(f"循环第 {i+1}/{times} 次")
                for sub_step in steps:
                    self._execute_step(sub_step)
                if interval > 0:
                    time.sleep(interval)
        
        elif mode == 'foreach':
            # 遍历循环
            items = step.get('items', [])
            item_var = step.get('item_var', 'item')
            item_scope = step.get('item_scope', 'local')
            
            logger.info(f"遍历循环: {len(items)} 个元素")
            for idx, item in enumerate(items):
                logger.info(f"循环第 {idx+1}/{len(items)} 次, {item_var}={item}")
                self._set_variable(item_var, item, item_scope)
                for sub_step in steps:
                    self._execute_step(sub_step)
                if interval > 0:
                    time.sleep(interval)
        
        elif mode == 'condition':
            # 条件循环
            left = step.get('left', '')
            operator = step.get('operator', '==')
            right = step.get('right', '')
            
            logger.info(f"条件循环: {left} {operator} {right}")
            loop_count = 0
            while loop_count < max_loops:
                left_val = self._render_value(left)
                right_val = self._render_value(right)
                
                # 评估条件
                condition = False
                if operator == '==':
                    condition = left_val == right_val
                elif operator == '!=':
                    condition = left_val != right_val
                
                if not condition:
                    break
                
                loop_count += 1
                logger.info(f"条件循环第 {loop_count} 次")
                for sub_step in steps:
                    self._execute_step(sub_step)
                if interval > 0:
                    time.sleep(interval)
    
    def _action_sequence(self, step: Dict[str, Any]):
        """顺序执行子步骤"""
        steps = step.get('steps', [])
        logger.info(f"顺序执行 {len(steps)} 个子步骤")
        for sub_step in steps:
            self._execute_step(sub_step)
    
    def _action_try(self, step: Dict[str, Any]):
        """异常处理：try/catch/finally"""
        try_steps = step.get('try_steps', [])
        catch_steps = step.get('catch_steps', [])
        finally_steps = step.get('finally_steps', [])
        error_var = step.get('error_var', 'error')
        error_scope = step.get('error_scope', 'local')
        
        logger.info("执行 try 块")
        try:
            for sub_step in try_steps:
                self._execute_step(sub_step)
        except Exception as e:
            logger.warning(f"捕获异常: {str(e)}")
            self._set_variable(error_var, str(e), error_scope)
            for sub_step in catch_steps:
                self._execute_step(sub_step)
        finally:
            logger.info("执行 finally 块")
            for sub_step in finally_steps:
                self._execute_step(sub_step)
    
    def _get_ocr_helper(self):
        """获取或创建 OCR Helper 实例"""
        if self._ocr_helper is None:
            if not OCR_AVAILABLE:
                raise RuntimeError("OCR 功能不可用，请安装: pip install easyocr opencv-python")
            self._ocr_helper = get_ocr_helper(languages=['en'], use_gpu=False)
        return self._ocr_helper
    
    
    def _action_foreach_assert(self, step: Dict[str, Any]):
        """循环点击断言（OCR）"""
        if not OCR_AVAILABLE:
            logger.warning("foreach_assert 需要 OCR 支持，请安装 easyocr")
            return
        
        try:
            # 从 config 中获取配置
            config = step.get('config', {})
            
            # 解析参数
            expected_list = config.get('expected_list', [])
            max_loops = config.get('max_loops', 5)
            interval = config.get('interval', 0.5)
            timeout = config.get('timeout', 5)
            match_mode = config.get('match_mode', 'contains')
            assert_type = config.get('assert_type', 'text')
            
            # 点击选择器
            click_selector_type = config.get('click_selector_type', 'image')
            click_selector = config.get('click_selector')
            click_config = {
                'selector_type': click_selector_type,
                'selector': click_selector,
                'image_scope': config.get('image_scope', 'common'),
                'image_threshold': config.get('image_threshold', 0.7)
            }
            click_target = self._resolve_selector(click_config)
            
            # OCR 区域选择器
            ocr_selector_type = config.get('ocr_selector_type', 'region')
            ocr_selector = config.get('ocr_selector')
            
            if not click_target:
                raise ValueError("foreach_assert 需要有效的 click_selector")
            if not ocr_selector:
                raise ValueError("foreach_assert 需要 ocr_selector 参数")
            
            # 解析 OCR 区域坐标
            if ocr_selector_type == 'region':
                if isinstance(ocr_selector, str):
                    parts = [int(p.strip()) for p in ocr_selector.split(',')]
                    if len(parts) != 4:
                        raise ValueError(f"OCR region 格式错误: {ocr_selector}")
                    ocr_region = tuple(parts)
                else:
                    ocr_region = tuple(ocr_selector)
            else:
                raise ValueError(f"foreach_assert 仅支持 ocr_selector_type=region")
            
            # OCR 识别
            ocr = self._get_ocr_helper()
            
            # 循环点击并断言
            matched_count = 0
            min_match = int(step.get('min_match', 1) or 0)
            for i in range(max_loops):
                logger.info(f"循环点击断言 第 {i+1}/{max_loops} 次")
                
                # 点击
                touch(click_target)
                time.sleep(interval)
                
                # OCR 识别
                if assert_type == 'number':
                    actual_value = ocr.recognize_region_number(ocr_region)
                else:
                    actual_value = ocr.recognize_region_text(ocr_region)
                
                # 检查是否匹配期望列表中的任何值
                matched = False
                for expected in expected_list:
                    if assert_type == 'number':
                        expected_num = int(str(expected).replace(',', ''))
                        if actual_value == expected_num:
                            matched = True
                            break
                    else:
                        if match_mode == 'exact':
                            if actual_value == expected:
                                matched = True
                                break
                        elif match_mode == 'contains':
                            if expected in actual_value:
                                matched = True
                                break
                
                if matched:
                    matched_count += 1
                    logger.info(f"第 {i+1} 次匹配成功: {actual_value} 在期望列表中")
                else:
                    logger.warning(f"第 {i+1} 次未匹配: {actual_value} 不在期望列表中")
            
            logger.info(f"循环点击断言完成: 共 {max_loops} 次，匹配 {matched_count} 次")
            if matched_count < min_match:
                raise AssertionError(
                    f"循环点击断言失败: 期望至少匹配 {min_match} 次，实际 {matched_count} 次"
                )
            
        except Exception as e:
            logger.error(f"foreach_assert 执行失败: {str(e)}")
            raise
