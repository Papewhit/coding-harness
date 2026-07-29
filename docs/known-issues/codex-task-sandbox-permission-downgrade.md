# Codex task 在 Git 权限拒绝后持续请求 approval

## 现象

在 Windows Codex Desktop 中，长期存在的 worktree task 可能在一次 Git
权限拒绝后持续以受限 sandbox 运行。即使当前主 task 已切换到 full access，
向旧 task 发送 follow-up 也可能继续出现以下现象：

- `git switch`、`git add`、`git commit` 等 Git 写操作反复请求 command approval；
- 随后连 worktree 内普通文件编辑也请求 approval；
- `safe.directory`、NTFS ACL 和 worktree 所属用户均已正确，但问题仍然存在；
- 同一项目中新建的 task 可以正常写入，只有旧 task 受影响。

这不是仓库代码、Git `safe.directory` 或单个文件权限问题。若普通 file edit
也触发 approval，应优先检查 task 自身的持久 sandbox profile。

## 已确认的原因

Codex 会按 task 保存权限状态。出现问题的 task 曾观察到如下状态：

```json
{
  "activePermissionProfile": null,
  "approvalPolicy": "on-request",
  "sandboxPolicy": {
    "type": "workspaceWrite",
    "writableRoots": [
      "<task-visualization-directory>"
    ]
  }
}
```

这里的 `writableRoots` 只有 visualization 目录，不包含实际代码 worktree。
因此普通文件编辑就会越过 sandbox；Git 写操作还会访问主仓库中的 linked-worktree
元数据，更容易首先暴露问题。

正常的 full-access task 则会显示等价于以下状态：

```json
{
  "activePermissionProfile": {
    "id": ":danger-full-access"
  },
  "approvalPolicy": "never",
  "sandboxPolicy": {
    "type": "dangerFullAccess"
  }
}
```

关键点是：follow-up 会复用原 task 的执行环境，不应假定它会继承当前主 task
的新权限设置。NTFS ACL、Codex capability SID 或 `safe.directory` 正常，也不能
覆盖 task 层的 `workspaceWrite` 策略。

目前证据能够确认“Git 权限拒绝后观察到 task 持久权限降级”这一故障链，但不能证明
Git 拒绝必然是唯一触发器。排查时应把 Git 拒绝视为常见前兆，而不是根因本身。

## 快速判断

按以下顺序判断，避免反复批准无效请求：

1. 查看 approval 对应的动作。若从 Git 写操作扩展到普通 file edit，停止处理
   `safe.directory`。
2. 对比同一项目中正常 task 与异常 task 的 permission profile。
3. 确认异常 task 的 `writableRoots` 是否包含真实 worktree。
4. 使用 `git worktree list --porcelain` 确认 linked worktree 的 Git 元数据仍位于
   主仓库；仅允许写代码目录可能不足以完成 Git 写操作。
5. 只读检查 worktree ACL。ACL 已允许写入但 file edit 仍请求 approval 时，
   应将问题归类为 task sandbox 配置错误。

Codex Desktop 的本地状态文件可能包含 prompt history 等敏感上下文。诊断时只读取
目标 task 的精确权限字段，不要整体输出、复制或提交该文件。

## 恢复方法

优先使用 Codex UI 或受支持的 task-permission 操作，将目标 task 切换到用户明确授权的
权限 profile。不要因为排障方便而擅自扩大权限。

切换后：

1. 拒绝或取消已经悬挂的旧 approval；活动中的 tool call 可能仍捕获旧策略。
2. 新开同一 task 的 follow-up turn。
3. 先做一个可回滚的 worktree 内写入检查，再执行 Git 写操作。
4. 对 linked worktree，分别验证普通文件写入和 Git index/ref 写入。

如果当前 Codex 版本没有更新既有 task 权限的受支持 API：

- 不要直接修改 Codex 的持久状态文件；运行中的主进程可能立即用内存状态覆盖它；
- 不要通过反复添加 `safe.directory`、修改全局 Git 配置或逐条 approval 掩盖问题；
- 暂停该 task 的写操作，由它只读返回变更或证据，再由已授权的协调 task 完成落盘；
- 只有在项目流程允许时，才创建具有正确权限的新 task；不要静默改变任务所有权。

## 预防

- 创建 worktree task 后立即核验其 permission profile，不依赖隐式继承。
- 首次执行前分别检查 worktree 文件写入与 Git 元数据写入。
- 发生 Git 权限拒绝后，在重试前重新核验 task sandbox；不要先假定是
  `safe.directory`。
- 对长生命周期 task，每次 remediation、resume 或 follow-up 前重新确认权限 profile。
- 记录权限异常和恢复方式，但不要把本机 SID、用户名、绝对路径或 Codex 本地状态文件
  写入仓库。

## 不应采用的处理方式

- 为消除弹窗而批准通配命令或不受限的递归文件操作；
- 重复写入全局 `safe.directory`；
- 把 file edit approval 误判为 Git ownership 问题；
- 直接编辑正在运行的 Codex 全局状态文件并假设会热加载；
- 在没有用户授权时把受限 task 改为 full access；
- 因权限问题删除原 worktree、branch 或 task。
