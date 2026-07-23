# 🍪 Twitter Cookie 获取指南

twt-audio-mcp 需要你的 Twitter Cookie 来抓取推文。  
**这些 Cookie 只存本地，不会上传，不会泄露。**

---

## 方法一：Chrome 开发者工具（推荐）

1. 打开 Chrome，登录 [x.com](https://x.com)
2. 按 `F12` 打开开发者工具
3. 点顶部的 **Application** 标签
   - 如果没看到，点 `>>` 展开更多标签
4. 左侧栏找到 **Cookies** → 点击 `https://x.com`
5. 在右侧表格中找到以下三个值：

| Name | 从哪里找 |
|------|---------|
| `auth_token` | 直接找这一行，复制 Value 列的 `auth_token` |
| `ct0` | 直接找这一行，复制 Value 列的 `ct0` |
| `twid` | 直接找这一行，复制 Value 列的 `twid` |

6. 运行 `bash setup.sh --cookie` 交互式输入

## 方法二：EditThisCookie 扩展

1. 安装 [EditThisCookie](https://chrome.google.com/webstore/detail/editthiscookie/fngmhnnpilhplaeedifhccceomclgfbg)
2. 登录 [x.com](https://x.com)
3. 点浏览器右上角的饼干图标
4. 导出 JSON，复制 `auth_token`、`ct0`、`twid` 到项目配置文件

## Cookie 文件格式

最终 `data/secrets/x_cookies.json` 应该是这样：

```json
{
  "auth_token": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "ct0": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "twid": "xxxxxxxxx"
}
```

---

## ⚠️ 注意事项

- **Cookie 会过期** — 几个月后需要重新获取
- **不要分享这个文件** — 别人能用你的身份发推
- **已加入 .gitignore** — 不会提交到 GitHub
- **多账号** — 用哪个账号登录 x.com，抓取就是那个账号的可见范围
