const express = require('express')
const cors = require('cors')
const multer = require('multer')
const path = require('path')

const app = express()
const PORT = 3001

// 中间件
app.use(cors())
app.use(express.json())
app.use(express.urlencoded({ extended: true }))

// 文件上传配置
const storage = multer.diskStorage({
  destination: function (req, file, cb) {
    cb(null, 'uploads/')
  },
  filename: function (req, file, cb) {
    cb(null, Date.now() + '-' + file.originalname)
  }
})

const upload = multer({ 
  storage: storage,
  limits: { fileSize: 10 * 1024 * 1024 }, // 10MB限制
  fileFilter: function (req, file, cb) {
    const allowedTypes = /jpeg|jpg|png|gif|pdf|doc|docx|txt/
    const extname = allowedTypes.test(path.extname(file.originalname).toLowerCase())
    const mimetype = allowedTypes.test(file.mimetype)
    
    if (mimetype && extname) {
      return cb(null, true)
    } else {
      cb(new Error('不支持的文件类型'))
    }
  }
})

// 创建上传目录
const fs = require('fs')
if (!fs.existsSync('uploads')) {
  fs.mkdirSync('uploads')
}

// 登录接口
app.post('/api/login', (req, res) => {
  const { username, password } = req.body
  
  // 模拟登录验证
  if (username && password && password.length >= 6) {
    res.json({
      success: true,
      message: '登录成功',
      data: {
        token: 'mock-token-' + Date.now(),
        user: {
          id: 1,
          username: username,
          email: username + '@example.com'
        }
      }
    })
  } else {
    res.status(401).json({
      success: false,
      message: '用户名或密码错误'
    })
  }
})

// 文件上传接口
app.post('/api/upload', upload.single('file'), (req, res) => {
  if (!req.file) {
    return res.status(400).json({
      success: false,
      message: '没有上传文件'
    })
  }
  
  res.json({
    success: true,
    message: '文件上传成功',
    data: {
      filename: req.file.filename,
      originalname: req.file.originalname,
      size: req.file.size,
      path: req.file.path
    }
  })
})

// LLM对话接口
app.post('/api/chat', async (req, res) => {
  const { message, model, file } = req.body
  
  if (!message) {
    return res.status(400).json({
      success: false,
      message: '消息内容不能为空'
    })
  }
  
  // 模拟AI处理时间
  await new Promise(resolve => setTimeout(resolve, 1000 + Math.random() * 2000))
  
  // 模拟AI回复
  const responses = [
    `我理解您的意思。关于"${message}"，我认为这是一个很有意思的问题。让我为您详细分析一下：`,
    `您提到的"${message}"让我想到了相关的解决方案。根据我的经验，您可以这样处理：`,
    `关于"${message}"，这是一个常见的需求。我建议您按照以下步骤操作：`,
    `感谢您提出这个问题。"${message}"涉及到多个方面，让我为您逐一解释：`
  ]
  
  let aiResponse = responses[Math.floor(Math.random() * responses.length)]
  
  if (file) {
    aiResponse = `我已经收到了您上传的文件"${file.name}"。` + aiResponse
  }
  
  // 根据模型返回不同的回复风格
  const modelConfigs = {
    'gpt-3.5-turbo': { prefix: 'GPT-3.5 Turbo回复：', style: '简洁明了' },
    'gpt-4': { prefix: 'GPT-4回复：', style: '详细深入' },
    'ernie-bot': { prefix: '文心一言回复：', style: '中文优化' },
    'qwen': { prefix: '通义千问回复：', style: '智能理解' }
  }
  
  const config = modelConfigs[model] || modelConfigs['gpt-3.5-turbo']
  aiResponse = config.prefix + '\n\n' + aiResponse + '\n\n这是一个基于' + config.style + '风格的回复。'
  
  res.json({
    success: true,
    message: '回复成功',
    data: {
      response: aiResponse,
      model: model,
      timestamp: new Date().toISOString()
    }
  })
})

// 获取模型列表
app.get('/api/models', (req, res) => {
  res.json({
    success: true,
    message: '获取模型列表成功',
    data: [
      { label: 'GPT-3.5 Turbo', value: 'gpt-3.5-turbo' },
      { label: 'GPT-4', value: 'gpt-4' },
      { label: '文心一言', value: 'ernie-bot' },
      { label: '通义千问', value: 'qwen' }
    ]
  })
})

// 健康检查
app.get('/api/health', (req, res) => {
  res.json({
    success: true,
    message: '服务运行正常',
    timestamp: new Date().toISOString()
  })
})

// 错误处理中间件
app.use((error, req, res, next) => {
  console.error('Error:', error)
  
  if (error instanceof multer.MulterError) {
    if (error.code === 'LIMIT_FILE_SIZE') {
      return res.status(400).json({
        success: false,
        message: '文件大小超过限制（10MB）'
      })
    }
  }
  
  res.status(500).json({
    success: false,
    message: error.message || '服务器内部错误'
  })
})

// 404处理
app.use((req, res) => {
  res.status(404).json({
    success: false,
    message: '接口不存在'
  })
})

app.listen(PORT, () => {
  console.log(`服务器运行在 http://localhost:${PORT}`)
  console.log('可用接口：')
  console.log('POST /api/login - 用户登录')
  console.log('POST /api/upload - 文件上传')
  console.log('POST /api/chat - AI对话')
  console.log('GET  /api/models - 获取模型列表')
  console.log('GET  /api/health - 健康检查')
})

module.exports = app