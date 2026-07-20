# W4 — Native Core Exchange 并行集成

三个 disjoint owner：Engine batch loop、Session exchange/private continuation、Structured ModelRequest/Context。都以 Scripted Native Client 验证，不调用在线模型。

Exit Gate：三个 lane 可在相同集成 SHA 编译和测试；`runtime.py` 架构预算不得通过放宽测试解决。
