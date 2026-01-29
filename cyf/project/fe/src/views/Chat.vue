<template>
  <div class="chat-container">
    <!-- 顶部导航栏 -->
    <div class="chat-header">
      <div class="header-left">
        <el-button
          class="sidebar-toggle-btn"
          :icon="sidebarCollapsed ? Expand : Fold"
          circle size="small"
          @click="sidebarCollapsed = !sidebarCollapsed"
        />
        <h2>智能对话</h2>
        <span class="user-info">用户：{{ authStore.user }}</span>
      <!-- 用量查询弹窗 -->
      <el-popover
        placement="bottom"
        :width="300"
        trigger="click"
        v-model:visible="showUsagePopover"
      >
        <template #reference>
          <el-button
            class="usage-btn"
            :icon="Coin"
            size="small"
            @click="fetchUsage"
          >
            查看用量
          </el-button>
        </template>
        <div class="usage-content">
          <div v-if="loadingUsage" class="loading">
            <el-icon class="is-loading"><Loading /></el-icon>
            正在加载用量数据...
          </div>
          <div v-else-if="usageError" class="error">
            {{ usageError }}
          </div>
          <div v-else class="usage-data">
            <!--  api查询范围条件有问题，先不展示-->
            <!-- <div class="usage-item">
              <span class="label">本日用量：</span>
              <span class="value">{{ usageData.today_usage }} 元</span>
            </div>
            <div class="usage-item">
              <span class="label">本周用量：</span>
              <span class="value">{{ usageData.week_usage }} 元</span>
            </div> -->
            <div class="usage-item">
              <span class="label">总用量：</span>
              <span class="value">{{ usageData.total_usage }} 元</span>
            </div>
            <div class="usage-item">
              <span class="label">总额度：</span>
              <span class="value">{{ usageData.quota > 10000? '-' : usageData.quota }} 元</span>
            </div>
            <div class="usage-item" :class="{ 'low-balance': usageData.remaining < 10 }">
              <span class="label">余    额：</span>
              <span class="value">{{ usageData.remaining > 10000? '-' : usageData.remaining }} 元</span>
            </div>
          </div>
        </div>
      </el-popover>
        <!-- TODO(human): 在此处添加用户信息和操作按钮，确保在移动端布局正确 -->
        <!-- 已完成: 移动端按钮并排显示优化 -->
      </div>
      <div class="header-right">
        <!-- LaTeX 公式帮助按钮 - 使用问号图标 -->
        <el-tooltip content="专业输出帮助" placement="top" popper-class="custom-dark-tooltip">
          <el-button
            :icon="QuestionFilled"
            circle
            size="small"
            @click="showLatexHelp"
          />
        </el-tooltip>
        <!-- 主题切换按钮 -->
        <el-button
          class="theme-toggle-btn"
          :icon="themeIcon"
          circle
          size="small"
          @click="toggleTheme"
        />
        <el-button
          type="danger"
          size="small"
          :icon="SwitchButton"
          @click="handleLogout"
        >
          退出登录
        </el-button>
      </div>
    </div>

    <!-- 聊天主体区域 -->
    <div class="chat-main">
      <!-- 侧边栏 -->
      <transition name="sidebar-slide">
        <div v-show="!sidebarCollapsed" class="chat-sidebar" :class="{ 'sidebar-mobile': isMobile }">
          <el-button v-if="isMobile" class="sidebar-close-btn" :icon="Close" circle @click="sidebarCollapsed = true"/>
          <div class="model-selector" @click.stop>
            <h3>选择模型</h3>
            <div class="provider-selector">
              <el-select
                v-model="providerValue"
                placeholder="选择厂商"
                size="small"
                filterable
                clearable
                @change="handleProviderChange"
              >
                <el-option
                  v-for="provider in providers"
                  :key="provider"
                  :label="provider"
                  :value="provider"
                />
              </el-select>
            </div>
            <div class="model-selector">
              <el-select
                v-model="modelValue"
                placeholder="选择模型"
                size="small"
                filterable
                clearable
                :disabled="!providerValue"
                @change="handleModelChange"
              >
                <el-option
                  v-for="model in filteredModels"
                  :key="model.value"
                  :value="model.value"
                >
                  <span>{{ model.label }}</span>
                  <el-tag v-if="model.recommend" size="small" type="warning" style="margin-left: 8px;">荐</el-tag>
                </el-option>
              </el-select>
            </div>
          </div>
          <div class="dialog-history-section">
            <!-- 显示选中模型的描述 -->
            <div v-if="currentModelDesc" class="model-description">
              <div class="model-desc-text">
                <el-icon><InfoFilled /></el-icon>
                <span>{{ currentModelDesc }}</span>
              </div>
            </div>
          </div>

          <div class="dialog-history-section">
            <div class="history-section-header">
              <h3>对话历史</h3>
              <div class="history-actions">
                <el-button
                  v-if="!isEditMode"
                  type="primary"
                  size="small"
                  text
                  @click="enterEditMode"
                >
                  编辑
                </el-button>
                <div v-else class="edit-mode-actions">
                  <el-button
                    type="danger"
                    size="small"
                    :disabled="selectedDialogs.length === 0"
                    @click="confirmBatchDelete"
                  >
                    删除 ({{ selectedDialogs.length }})
                  </el-button>
                  <el-button
                    size="small"
                    @click="exitEditMode"
                  >
                    取消
                  </el-button>
                </div>
              </div>
            </div>
            <el-button
              type="primary"
              size="small"
              @click="loadDialogHistory"
              :loading="loadingHistory"
              style="margin-bottom: 10px;"
            >
              <el-icon><Refresh /></el-icon>
              刷新历史
            </el-button>
            <div class="dialog-list">
              <div
                v-for="dialog in dialogHistory"
                :key="dialog.id"
                class="dialog-item"
                :class="{ 'selected': isEditMode && selectedDialogs.includes(dialog.id) }"
                @click="isEditMode ? toggleSelectDialog(dialog.id) : loadDialogContent(dialog.id)"
              >
                <el-checkbox
                  v-if="isEditMode"
                  v-model="selectedDialogs"
                  :label="dialog.id"
                  @click.stop
                  class="dialog-checkbox"
                />
                <div class="dialog-content" @click.stop="!isEditMode && loadDialogContent(dialog.id)">
                  <el-tooltip
                    :content="dialog.dialog_name"
                    :disabled="!shouldShowTooltip(dialog.dialog_name, 'title')"
                    placement="top"
                    popper-class="custom-dark-tooltip"
                  >
                    <div
                      class="dialog-title"
                      :style="{ maxWidth: '100%' }"
                    >
                      {{ dialog.dialog_name }}
                    </div>
                  </el-tooltip>
                  <div class="dialog-info">
                    <el-tooltip
                      :content="dialog.modelname"
                      :disabled="!shouldShowTooltip(dialog.modelname, 'model')"
                      placement="top"
                      popper-class="custom-dark-tooltip"
                    >
                      <div
                        class="dialog-model"
                        :style="{ maxWidth: '80px' }"
                      >
                        {{ dialog.modelname }}
                      </div>
                    </el-tooltip>
                    <div class="dialog-date">{{ dialog.start_date }}</div>
                  </div>
                </div>
                <el-popconfirm
                  v-if="!isEditMode"
                  title="确定要删除这个对话吗？"
                  confirm-button-text="确定"
                  cancel-button-text="取消"
                  @confirm="confirmSingleDelete(dialog.id)"
                  @cancel.stop
                >
                  <template #reference>
                    <el-button
                      v-if="!isEditMode"
                      class="delete-btn"
                      :icon="Delete"
                      circle
                      size="small"
                      text
                      @click.stop
                    />
                  </template>
                </el-popconfirm>
              </div>
              <div v-if="dialogHistory.length === 0" class="no-dialogs">
                暂无历史对话
              </div>
            </div>
          </div>

          <!-- 上下文设置部分 -->
          <div class="context-settings-section">
            <h3>上下文设置</h3>
            <div class="context-slider-wrapper">
              <div class="context-label">
                <span>携带历史消息</span>
                <el-tag size="small" type="info">{{ contextCount }} 条</el-tag>
              </div>
              <el-slider v-model="contextCount" :min="0" :max="50" :step="1"
                :marks="{ 0: '0', 25: '25', 50: '50' }"/>
              <div class="context-hint">设为0时仅发送当前消息</div>
            </div>

            <!-- 最大回复字数 -->
            <div class="context-slider-wrapper">
              <div class="context-label">
                <span>最大回复字数（仅供参考）</span>
                <el-tag size="small" type="info">{{ maxResponseChars }} 字</el-tag>
              </div>
              <el-slider v-model="maxResponseChars" :min="500" :max="32000" :step="500"
                :marks="{ 500: '500', 8000: '8千', 30000: '3万' }" />
              <div class="context-hint">限制AI回复的最大长度</div>
            </div>

            <!-- 流式输出开关 -->
            <div class="context-switch-wrapper">
              <div class="context-label">
                <span>逐字输出</span>
                <el-switch
                  v-model="streamEnabled"
                  active-text="开启"
                  inactive-text="关闭"
                  size="default"
                />
              </div>
              <div class="context-hint">开启时逐字逐句显示AI回复，关闭时等待完整回复</div>
            </div>
          </div>

          <!-- 角色设定部分 -->
          <div class="system-prompt-section">
            <h3>角色设定</h3>
            <el-input
              v-model="systemPrompt"
              type="textarea"
              :rows="3"
              :disabled="enhancedRoleEnabled"
              placeholder="输入系统提示词，例如：你是一个专业的程序员助手..."
              resize="vertical"
              @blur="handleSystemPromptBlur"
            />
            <div class="system-prompt-hint">设定 AI 的行为和角色</div>

            <!-- 角色设定选项卡 - 当启用增强角色时禁用 -->
            <div :class="{ 'role-tabs': true, 'disabled': enhancedRoleEnabled }">
              <div
                v-for="role in rolePresets"
                :key="role.id"
                class="role-tab"
                :class="{ active: activeRoleId === role.id }"
              >
                <span @click="switchRole(role)">{{ role.name }}</span>
                <div class="role-tab-actions" v-if="!['default', 'programmer', 'translator', 'writer'].includes(role.id)">
                  <el-dropdown trigger="click" @command="(command: string) => handleRoleAction(command, role.id)">
                    <el-button text size="small" class="role-action-btn">
                      <el-icon><MoreFilled /></el-icon>
                    </el-button>
                    <template #dropdown>
                      <el-dropdown-menu>
                        <el-dropdown-item command="rename">
                          <el-icon><EditPen /></el-icon>
                          重命名
                        </el-dropdown-item>
                        <el-dropdown-item command="delete" divided>
                          <el-icon><Delete /></el-icon>
                          删除
                        </el-dropdown-item>
                      </el-dropdown-menu>
                    </template>
                  </el-dropdown>
                </div>
              </div>
              <div class="role-tab add-tab" @click="addCustomRole">
                <el-icon><Plus /></el-icon>
              </div>
            </div>

            <!-- 增强角色选择 -->
            <div class="enhanced-role-section">
              <div class="enhanced-role-toggle">
                <el-checkbox
                  v-model="enhancedRoleEnabled"
                  @change="handleEnhancedRoleToggle"
                >
                  启用增强角色
                </el-checkbox>
                <el-icon v-if="loadingEnhancedRoles" class="is-loading">
                  <Loading />
                </el-icon>
              </div>

              <!-- 增强角色界面，只有在启用时才显示 -->
              <div v-if="enhancedRoleEnabled" class="enhanced-role-interface">
                <!-- 分组标签 -->
                <el-tabs
                  v-model="activeEnhancedGroup"
                  type="card"
                  @tab-change="handleGroupChange"
                >
                  <el-tab-pane
                    v-for="(roles, groupName) in enhancedRoleGroups"
                    :key="groupName"
                    :label="groupName"
                    :name="groupName"
                  >
                  </el-tab-pane>
                </el-tabs>

                <!-- 角色列表 -->
                <div v-if="activeEnhancedGroup && enhancedRoleGroups[activeEnhancedGroup]" class="enhanced-role-list">
                  <el-radio-group v-model="selectedEnhancedRole" @change="handleEnhancedRoleSelect">
                    <div
                      v-for="role in enhancedRoleGroups[activeEnhancedGroup]"
                      :key="role.role_name"
                      class="enhanced-role-item"
                    >
                      <el-radio :value="role.role_name" border class="enhanced-role-radio">
                        <div class="role-info">
                          <div class="role-name">{{ role.role_name }}</div>
                          <div class="role-desc">{{ role.role_desc }}</div>
                        </div>
                      </el-radio>
                    </div>
                  </el-radio-group>
                </div>
              </div>
            </div>
          </div>

          <!-- 发送键偏好设置 -->
          <div class="send-preference-section">
            <h3>发送设置</h3>
            <div class="send-preference-wrapper">
              <el-switch
                v-model="sendPreference"
                :active-value="'enter'"
                :inactive-value="'ctrl_enter'"
                active-text="Enter发送"
                inactive-text="Ctrl+Enter发送"
              />
              <div class="send-preference-hint">
                当前: {{ sendPreference === 'enter' ? '直接按Enter发送' : '按Ctrl+Enter发送' }}
              </div>
            </div>
          </div>
        </div>
      </transition>
      <div v-if="isMobile && !sidebarCollapsed" class="sidebar-overlay" @click="sidebarCollapsed = true"/>

      <!-- 聊天内容区域 -->
      <div class="chat-content">
        <div class="chat-toolbar">
          <!-- 在桌面端显示完整toolbar，在移动端显示抽屉切换按钮 -->
          <div v-if="!isMobile" class="toolbar-desktop">
            <!-- 新增：对话标题编辑区域 -->
            <div class="dialog-title-editor">
              <el-input
                v-model="dialogTitle"
                placeholder="请输入对话标题..."
                size="small"
                @blur="handleTitleBlur"
              />
              <!-- 更新标题按钮：当有当前对话ID时显示 -->
              <el-button
                v-if="currentDialogId"
                type="primary"
                size="small"
                @click="updateDialogTitle"
                class="update-title-btn"
                :disabled="!dialogTitle.trim()"
              >
                更新标题
              </el-button>
            </div>

            <!-- 新增：字体大小控制 -->
            <div class="font-size-controls">
              <span class="font-size-label">文字大小:</span>
              <el-tooltip content="文字大小" placement="bottom">
                <el-radio-group v-model="fontSize" size="small" @change="handleFontSizeChange">
                  <el-radio-button label="small">小</el-radio-button>
                  <el-radio-button label="medium">中</el-radio-button>
                  <el-radio-button label="large">大</el-radio-button>
                </el-radio-group>
              </el-tooltip>
            </div>

            <div class="action-buttons">
              <el-button
                type="warning"
                size="small"
                @click="clearCurrentSession"
              >
                <el-icon><CirclePlus /></el-icon>
                开启另一个会话
              </el-button>

              <!-- 新增：导出对话截屏按钮 -->
              <el-button
                type="primary"
                size="small"
                @click="exportConversationScreenshot"
              >
                <el-icon><Download /></el-icon>
                导出对话截图
              </el-button>
            </div>
          </div>

          <!-- 移动端：显示抽屉切换按钮 -->
          <div v-else class="toolbar-mobile">
            <el-button
              icon="Menu"
              size="default"
              circle
              @click="showToolbarDrawer = true"
              class="mobile-toolbar-btn"
            />
          </div>

          <!-- 移动端抽屉菜单 -->
          <el-drawer
            v-if="isMobile"
            v-model="showToolbarDrawer"
            title="工具栏"
            direction="rtl"
            size="80%"
            :destroy-on-close="true"
            :close-on-click-modal="true"
          >
            <div class="mobile-toolbar-content">
              <!-- 对话标题编辑区域 -->
              <div class="dialog-title-editor">
                <span class="mobile-form-label">对话标题</span>
                <el-input
                  v-model="dialogTitle"
                  placeholder="请输入对话标题..."
                  size="default"
                  @blur="handleTitleBlur"
                />
                <!-- 更新标题按钮：当有当前对话ID时显示 -->
                <el-button
                  v-if="currentDialogId"
                  type="primary"
                  size="default"
                  @click="updateDialogTitle"
                  class="update-title-btn-mobile"
                  :disabled="!dialogTitle.trim()"
                >
                  更新标题
                </el-button>
              </div>

              <!-- 字体大小控制 -->
              <div class="font-size-controls">
                <span class="mobile-form-label">文字大小</span>
                <el-radio-group v-model="fontSize" size="default" @change="handleFontSizeChange">
                  <el-radio-button label="small">小</el-radio-button>
                  <el-radio-button label="medium">中</el-radio-button>
                  <el-radio-button label="large">大</el-radio-button>
                </el-radio-group>
              </div>

              <!-- 操作按钮 -->
              <div class="action-buttons">
                <el-button
                  type="warning"
                  size="default"
                  @click="clearCurrentSession"
                  class="drawer-button"
                >
                  <el-icon><CirclePlus /></el-icon>
                  开启另一个会话
                </el-button>

                <!-- 导出对话截屏按钮 -->
                <el-button
                  type="primary"
                  size="default"
                  @click="exportConversationScreenshot"
                  class="drawer-button"
                >
                  <el-icon><Download /></el-icon>
                  导出对话截图
                </el-button>
              </div>
            </div>
          </el-drawer>
        </div>
        <div class="messages-container" :class="'font-' + fontSize" ref="messagesContainer">
          <div
            v-for="(message, index) in messages"
            :key="index"
            :class="['message', message.type]"
          >
            <div class="message-avatar">
              <el-icon v-if="message.type === 'user'"><UserFilled /></el-icon>
              <el-icon v-else><Cpu /></el-icon>
            </div>
            <div class="message-content">
              <div class="message-header">
                <span class="message-author">{{ message.type === 'user' ? authStore.user : 'AI助手' }}</span>
                <span class="message-time">{{ message.time }}</span>
                <div class="message-actions">
                  <el-button
                    :icon="CopyDocument"
                    circle
                    size="small"
                    text
                    @click="copyMessageContent(message.content)"
                  />
                  <el-popconfirm
                    title="确定要删除这条消息吗？"
                    confirm-button-text="确定"
                    cancel-button-text="取消"
                    @confirm="deleteMessage(index)"
                  >
                    <template #reference>
                      <el-button
                        :icon="Delete"
                        circle
                        size="small"
                        text
                      />
                    </template>
                  </el-popconfirm>
                </div>
              </div>
              <div class="message-text" v-html="renderMarkdown(getTextContent(message.content))"></div>
              <!-- TODO(human): 添加响应式表格和代码块的移动端优化，确保在小屏幕上能够良好显示 -->
              <!-- 已完成: 代码块和表格的移动端响应式布局优化 -->
              <!-- 图片预览 -->
              <div v-if="extractFileUrls(message.content).length > 0" class="message-attachments">
                <template v-for="url in extractFileUrls(message.content)" :key="url">
                  <img
                    v-if="isImageUrl(url)"
                    :src="url"
                    class="attachment-preview"
                    @click="openImagePreview(url)"
                  />
                  <a v-else :href="url" target="_blank" class="attachment-link">
                    <el-icon><Document /></el-icon>
                    {{ url.split('/').pop() }}
                  </a>
                </template>
              </div>
              <!-- 流式内容的加载动画 -->
              <div v-if="message.type === 'ai' && isStreaming(index)" class="streaming-indicator">
                <hr class="divider" />
                <div v-if="message.content === ''" class="typing-initial">
                  <div class="typing-placeholder">
                    答案马上就到，不要担心！
                  </div>
                  <div class="typing">
                    <span class="typing-dot"></span>
                    <span class="typing-dot"></span>
                    <span class="typing-dot"></span>
                  </div>
                </div>
                <div v-else class="typing-continue">
                  <div class="typing">
                    <span class="typing-dot"></span>
                    <span class="typing-dot"></span>
                    <span class="typing-dot"></span>
                  </div>
                </div>
              </div>
              <!-- 错误消息重试按钮 -->
              <div v-if="message.type === 'ai' && message.isError" class="error-actions">
                <el-button
                  type="warning"
                  size="small"
                  @click="retryMessage(index)"
                >
                  <el-icon><RefreshLeft /></el-icon>
                  重试
                </el-button>
              </div>
              <!-- 当回复为空时，提示用户重新发送 -->
              <div v-if="message.type === 'ai' && message.content === '' && !message.isError && !isStreaming(index)" class="empty-response-actions">
                <el-alert
                  :closable="false"
                  title="AI助手暂时没有回复，请稍后再试或重新提问"
                  type="info"
                  show-icon
                />
                <el-button
                  type="primary"
                  size="small"
                  @click="retryMessage(index)"
                >
                  <el-icon><RefreshLeft /></el-icon>
                  重新提问
                </el-button>
              </div>
              <!-- 截断消息继续生成按钮 -->
              <div v-if="message.type === 'ai' && message.isTruncated && !message.isError && !isStreaming(index)" class="truncated-actions">
                <div class="truncated-indicator">
                  <span class="ellipsis">...</span>
                  <span class="truncated-hint">内容被截断</span>
                </div>
                <el-button type="primary" size="small" @click="continueGeneration(index)" :disabled="isLoading">
                  <el-icon><CaretRight /></el-icon>
                  继续生成
                </el-button>
              </div>
              <div v-if="message.file" class="message-file">
                <el-icon><Document /></el-icon>
                <span>{{ message.file.name }}</span>
              </div>
            </div>
          </div>

          <!-- 对话区域内嵌水印（用于长截图） -->
          <div class="copyright-watermark-inline">
            <span>© 2026 vyfe | aichat.609088523.xyz | vx:pata_data_studio</span>
          </div>

          <!-- 开源项目链接 -->
          <div class="github-link-inline">
            <a href="https://github.com/vyfe/openai-project" target="_blank" rel="noopener noreferrer">
              <el-icon><Link /></el-icon> 开源项目 GitHub
            </a>
            <span class="wechat-info"> vx:pata_data_studio </span>
          </div>

          <!-- 回到顶部按钮 -->
          <div
            v-if="showBackToTop"
            class="back-to-top-btn"
            @click="scrollToTop"
          >
            <el-icon><Top /></el-icon>
          </div>
        </div>

        <!-- 输入区域 -->
        <div class="input-area">
          <div class="input-container">
            <el-input
              v-model="inputMessage"
              type="textarea"
              :rows="3"
              :placeholder="`请输入您的问题... (${sendPreference === 'enter' ? '回车发送，Shift+回车换行' : '回车换行，Ctrl+回车发送'})`"
              class="message-input"
              @keydown="handleKeydown"
            />
            <div class="input-actions">
              <!-- 文件上传按钮移到输入框上方，右侧 -->
              <el-popover placement="top-start" :width="280" trigger="click" v-model:visible="showUploadPopover">
                <template #reference>
                  <el-button class="upload-trigger-btn" :icon="Plus" circle size="large"/>
                </template>
                <div class="upload-popover-content">
                  <div class="upload-popover-header">
                    <span>上传文件</span>
                    <el-button v-if="uploadedFile" type="danger" size="small" text @click="clearFile">清除</el-button>
                  </div>
                  <el-upload ref="uploadRef" drag :auto-upload="false" :on-change="handleFileChange"
                    accept=".txt,.pdf,.png,.jpg,.jpeg,.gif,.ppt,.pptx,.md,.markdown">
                    <el-icon><upload-filled /></el-icon>
                    <div class="el-upload__text">拖拽或点击上传</div>
                  </el-upload>
                </div>
              </el-popover>

            <el-button
              type="primary"
              :icon="Position"
              :disabled="!inputMessage.trim() || isLoading"
              @click="sendMessage"
            >
              发送
            </el-button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- 图片预览弹窗 -->
  <el-dialog
    v-model="showImagePreview"
    width="80%"
    top="5vh"
    class="image-preview-dialog"
    :modal="true"
    :show-close="true"
    @close="showImagePreview = false"
  >
    <img :src="previewImageUrl" style="width: 100%; height: auto;" />
  </el-dialog>

  <!-- 格式帮助弹窗 -->
  <el-dialog
    v-model="showLatexHelpDialog"
  
    width="60%"
    :modal="true"
    :show-close="true"
    @close="showLatexHelpDialog = false"
  >
    <div class="latex-help-content">
      <h2>专业输出帮助</h2>
      <h3>如何在对话中使用 LaTeX 数学公式</h3>
      <p>您可以使用以下语法在对话中插入数学公式：</p>

      <h4>内联公式（行内）</h4>
      <p>使用 <code>$...$</code> 包围公式，例如：<code>$E=mc^2$</code></p>

      <h4>独立公式（居中显示）</h4>
      <p>使用 <code>$$...$$</code> 包围公式，例如：<code>$$y = X\\beta + \\epsilon$$</code></p>

      <h4>示例</h4>
      <div class="example-formulas">
        <p><strong>二次公式：</strong> $x = \\frac{-b \\pm \\sqrt{b^2-4ac}}{2a}$</p>
        <p><strong>欧拉恒等式：</strong> $$e^{i\\pi} + 1 = 0$$</p>
        <p><strong>矩阵：</strong> $A = \\begin{bmatrix} a & b \\\\ c & d \\end{bmatrix}$</p>
      </div>

      <p>公式将在消息中自动渲染为美观的数学符号。</p>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, nextTick, onMounted, watch, onUnmounted, computed, onUpdated } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, ElCascader, ElDrawer } from 'element-plus'
import {
  SwitchButton,
  UploadFilled,
  UserFilled,
  Cpu,
  Document,
  Position,
  Refresh,
  Delete,
  Plus,
  Expand,
  Fold,
  Close,
  CopyDocument,
  RefreshLeft,
  MoreFilled,
  EditPen,
  Top,
  Link,
  Coin,
  Loading,
  Sunny,
  Moon,
  CaretRight,
  InfoFilled,
  QuestionFilled,
  Menu
} from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { chatAPI, fileAPI } from '@/services/api'
import { marked } from 'marked'
import hljs from 'highlight.js'
import 'highlight.js/styles/github-dark.css'
import katex from 'katex'
import 'katex/dist/katex.min.css'
import '@/views/styles/chat.css'
import VersionService from '@/services/version'

const router = useRouter()
const authStore = useAuthStore()
const messagesContainer = ref<HTMLElement>()
const uploadRef = ref()
const isLoading = ref(false)
const loadingHistory = ref(false)
const inputMessage = ref('')
const uploadedFile = ref<File | null>(null)
const showUploadPopover = ref(false)
const showLatexHelpDialog = ref(false)

// 添加对话标题状态
const dialogTitle = ref('')
// 添加当前对话ID状态
const currentDialogId = ref<number | null>(null)

// 添加字体大小控制 对话框
const fontSize = ref(localStorage.getItem('fontSize') || 'medium')

// 添加状态跟踪用户是否手动滚动离开了底部
const isScrolledToBottom = ref(true)

// 控制是否显示回到顶部按钮
const showBackToTop = ref(false)

// 添加用量查询相关状态
const showUsagePopover = ref(false)
const loadingUsage = ref(false)
const usageData = ref({
  today_usage: 0,
  week_usage: 0,
  total_usage: 0,
  quota: 0,
  remaining: 0,
  currency: 'CNY'
})
const usageError = ref('')

const selectedModel = ref(localStorage.getItem('selectedModel') || '')

// 添加上下文数量状态变量
const contextCount = ref(parseInt(localStorage.getItem('contextCount') || '10'))

// 最大回复字数（实际 token = 值 * 2）
const maxResponseChars = ref(parseInt(localStorage.getItem('maxResponseChars') || '8000'))

// 添加侧边栏折叠状态
const sidebarCollapsed = ref(JSON.parse(localStorage.getItem('sidebarCollapsed') || 'false'))
const isMobile = ref(false)
const showToolbarDrawer = ref(false)

// 流式输出开关
const streamEnabled = ref(JSON.parse(localStorage.getItem('streamEnabled') || 'true'))

// TODO(human): 添加发送键偏好设置，默认为 'ctrl_enter'，表示使用Ctrl+Enter发送；若为 'enter' 则直接按Enter发送
const sendPreference = ref(localStorage.getItem('sendPreference') || 'ctrl_enter')

// 用于检测软键盘是否激活的状态
const isKeyboardVisible = ref(false)

// 记录之前的设备类型状态
const previousIsMobile = ref(false)

// 实现移动端设备检测逻辑，当屏幕宽度小于768px时将isMobile设为true，并监听窗口大小变化
const checkIsMobile = () => {
  // 当窗口宽度小于768px时，认为是移动端
  const currentIsMobile = window.innerWidth < 768

  // 如果设备类型发生变化，则相应地调整抽屉状态
  if (currentIsMobile !== previousIsMobile.value) {
    // 在从桌面端切换到移动端时，不自动打开抽屉
    // 在从移动端切换到桌面端时，如果抽屉是打开的则关闭它
    if (!currentIsMobile && showToolbarDrawer.value) {
      showToolbarDrawer.value = false
    }
  }

  isMobile.value = currentIsMobile
  previousIsMobile.value = currentIsMobile
}

// 图片预览相关状态
const previewImageUrl = ref('')
const showImagePreview = ref(false)

// 打开图片预览
const openImagePreview = (url: string) => {
  previewImageUrl.value = url
  showImagePreview.value = true
}

// 角色设定（System Prompt）
const systemPrompt = ref(localStorage.getItem('systemPrompt') || '')

// 增强角色选择相关变量
const enhancedRoleEnabled = ref(JSON.parse(localStorage.getItem('enhancedRoleEnabled') || 'false'))
const enhancedRoleGroups = ref<Record<string, Array<{role_name: string, role_desc: string, role_content: string}>>>({})
const activeEnhancedGroup = ref(localStorage.getItem('activeEnhancedGroup') || '')
const selectedEnhancedRole = ref(localStorage.getItem('selectedEnhancedRole') || '')
const loadingEnhancedRoles = ref(false)

// 预设角色设定列表
const rolePresets = ref<Array<{id: string, name: string, prompt: string}>>([
  { id: 'default', name: '默认', prompt: '' },
  { id: 'translator', name: '翻译', prompt: '你是一个专业的翻译助手，擅长中英文互译，注重语义准确和表达流畅。' },
  { id: 'writer', name: '写作', prompt: '你是一个专业的写作助手，擅长文章润色、创意写作和文案编辑。' }
])

// 保存自定义角色到localStorage
const saveCustomRoles = () => {
  const customRoles = rolePresets.value.filter(
    role => !['default', 'programmer', 'translator', 'writer'].includes(role.id)
  )
  localStorage.setItem('customRoles', JSON.stringify(customRoles))
}

// 从localStorage加载自定义角色
const loadCustomRoles = () => {
  const saved = localStorage.getItem('customRoles')
  if (saved) {
    try {
      const customRoles = JSON.parse(saved)
      // 追加到预设角色后面
      rolePresets.value.push(...customRoles)
    } catch (e) {
      console.error('加载自定义角色失败:', e)
    }
  }
}

// 初始化时检测是否为移动端
onMounted(() => {
  checkIsMobile()

  // 监听窗口大小变化
  window.addEventListener('resize', checkIsMobile)
})

// 组件卸载时移除事件监听器
onUnmounted(() => {
  window.removeEventListener('resize', checkIsMobile)
})

// 主题相关状态
const isDarkTheme = ref(localStorage.getItem('isDarkTheme') === 'true')

// 根据主题状态选择图标
const themeIcon = computed(() => {
  return isDarkTheme.value ? Moon : Sunny
})

// 切换主题函数
const toggleTheme = () => {
  isDarkTheme.value = !isDarkTheme.value
  localStorage.setItem('isDarkTheme', isDarkTheme.value.toString())

  // 切换主题类到body元素
  if (isDarkTheme.value) {
    document.body.classList.add('dark-theme')
  } else {
    document.body.classList.remove('dark-theme')
  }

  ElMessage.success(isDarkTheme.value ? '已切换到深色主题' : '已切换到浅色主题')
}

// 在组件挂载时应用主题
onMounted(() => {
  if (isDarkTheme.value) {
    document.body.classList.add('dark-theme')
  } else {
    document.body.classList.remove('dark-theme')
  }
})

// 当前选中的角色ID
const activeRoleId = ref(localStorage.getItem('activeRoleId') || 'default')

// 当前增强角色内容的计算属性
const currentEnhancedRoleContent = computed(() => {
  if (activeEnhancedGroup.value && selectedEnhancedRole.value) {
    const group = enhancedRoleGroups.value[activeEnhancedGroup.value]
    if (group) {
      const role = group.find(r => r.role_name === selectedEnhancedRole.value)
      return role ? role.role_content : ''
    }
  }
  return ''
})

const models = ref<Array<{ label: string, value: string, recommend?: boolean, model_desc?: string }>>([])

// 添加当前模型描述的状态
const currentModelDesc = ref<string>('')

// 添加分组模型数据
const groupedModels = ref<Record<string, Array<{ label: string, value: string, recommend?: boolean, model_desc?: string }>>>({});

// 新增：独立的模型选择器状态
const providerValue = ref<string>('')
const modelValue = ref<string>('')
const providers = ref<string[]>([])
const filteredModels = computed(() => {
  if (!providerValue.value) return []
  // 根据当前选择的厂商过滤模型，并按推荐状态排序
  const providerModels = models.value.filter(model => {
    // 检查模型值是否包含厂商名称
    return model.value.toLowerCase().includes(providerValue.value.toLowerCase()) ||
           model.label.toLowerCase().includes(providerValue.value.toLowerCase())
  })

  // 按推荐状态排序：推荐的模型在前面
  return providerModels.sort((a, b) => {
    if (a.recommend && !b.recommend) return -1
    if (!a.recommend && b.recommend) return 1
    return 0
  })
})

// 对话历史数据
const dialogHistory = ref<any[]>([])

// TODO(human): 添加删除功能所需的状态变量
// 编辑模式状态
const isEditMode = ref(false)
// 已选择的对话ID列表
const selectedDialogs = ref<number[]>([])

// 监听contextCount变化并持久化
watch(contextCount, (newVal) => {
  localStorage.setItem('contextCount', newVal.toString())
})

// 监听maxResponseChars变化并持久化
watch(maxResponseChars, (newVal) => {
  localStorage.setItem('maxResponseChars', newVal.toString())
})

// 监听sidebarCollapsed变化并持久化
watch(sidebarCollapsed, (newVal) => {
  localStorage.setItem('sidebarCollapsed', JSON.stringify(newVal))
})

// 监听selectedModel变化并持久化
watch(selectedModel, (newVal) => {
  localStorage.setItem('selectedModel', newVal)
})

// 监听providerValue和modelValue变化，同步到selectedModel
watch([providerValue, modelValue], ([newProvider, newModel]) => {
  if (newProvider && newModel) {
    selectedModel.value = newModel
  } else if (!newProvider) {
    selectedModel.value = ''
  }
})

// 监听 systemPrompt 变化并更新当前角色的prompt
watch(systemPrompt, (newVal) => {
  // 更新当前选中角色的prompt内容
  const currentRole = rolePresets.value.find(r => r.id === activeRoleId.value)
  if (currentRole && !['default', 'programmer', 'translator', 'writer'].includes(currentRole.id)) {
    currentRole.prompt = newVal
    saveCustomRoles() // 保存自定义角色
  }
  localStorage.setItem('systemPrompt', newVal)
})

// 监听 enhancedRoleEnabled 变化并持久化
watch(enhancedRoleEnabled, (newVal) => {
  localStorage.setItem('enhancedRoleEnabled', JSON.stringify(newVal))
})

// 监听 activeEnhancedGroup 变化并持久化
watch(activeEnhancedGroup, (newVal) => {
  localStorage.setItem('activeEnhancedGroup', newVal)
})

// 监听 selectedEnhancedRole 变化并持久化
watch(selectedEnhancedRole, (newVal) => {
  localStorage.setItem('selectedEnhancedRole', newVal)
})

// 注释掉监听 dialogTitle 变化并持久化的功能，这样标题就不会保存到localStorage
// watch(dialogTitle, (newVal) => {
//   localStorage.setItem('dialogTitle', newVal)
// })

// 监听 fontSize 变化并持久化
watch(fontSize, (newVal) => {
  localStorage.setItem('fontSize', newVal)
})

// 监听 sendPreference 变化并持久化
watch(sendPreference, (newVal) => {
  localStorage.setItem('sendPreference', newVal)
})

// 监听 streamEnabled 变化并持久化
watch(streamEnabled, (newVal) => {
  localStorage.setItem('streamEnabled', JSON.stringify(newVal))
})

// 监听 activeRoleId 变化并持久化
watch(activeRoleId, (newVal) => {
  localStorage.setItem('activeRoleId', newVal)
})

// 切换角色函数
const switchRole = (role: {id: string, name: string, prompt: string}) => {
  activeRoleId.value = role.id
  systemPrompt.value = role.prompt
  localStorage.setItem('activeRoleId', role.id)
  localStorage.setItem('systemPrompt', role.prompt) // 同时保存当前prompt到localStorage
}

// 添加自定义角色函数
const addCustomRole = () => {
  // 添加自定义角色的逻辑
  const newId = `custom_${Date.now()}`
  rolePresets.value.push({
    id: newId,
    name: '自定义',
    prompt: systemPrompt.value
  })
  activeRoleId.value = newId
  localStorage.setItem('activeRoleId', newId)
  localStorage.setItem('systemPrompt', systemPrompt.value) // 同时保存当前prompt到localStorage
  saveCustomRoles() // 保存自定义角色
}

// 从消息内容中提取文件URL列表（兼容新旧格式）
const extractFileUrls = (content: string): string[] => {
  const urls: string[] = []

  // 新格式: [FILE_URL:xxx]
  const newPattern = /\[FILE_URL:(https?:\/\/[^\]]+)\]/g
  let match
  while ((match = newPattern.exec(content)) !== null) {
    urls.push(match[1])
  }

  // 旧格式: 文件已上传: xxx (向后兼容)
  const oldPattern = /文件已上传:\s*(https?:\/\/[^\s]+)/g
  while ((match = oldPattern.exec(content)) !== null) {
    urls.push(match[1])
  }

  return urls
}

// 获取纯文本内容（移除文件标记）
const getTextContent = (content: string): string => {
  return content.replace(/\[(FILE_URL|文件已上传):[^\]]+\]/g, '').trim()
}

// 判断URL是否为图片
const isImageUrl = (url: string): boolean => {
  return /\.(png|jpg|jpeg|gif|webp|bmp|svg)(\?.*)?$/i.test(url)
}

// 处理系统提示词输入框失焦事件
const handleSystemPromptBlur = () => {
  // 更新当前选中角色的prompt内容
  const currentRole = rolePresets.value.find(r => r.id === activeRoleId.value)
  if (currentRole && !['default', 'programmer', 'translator', 'writer'].includes(currentRole.id)) {
    currentRole.prompt = systemPrompt.value
    saveCustomRoles() // 保存自定义角色
  }
}

// 加载增强角色数据
const loadEnhancedRoles = async () => {
  if (!enhancedRoleEnabled.value) return

  loadingEnhancedRoles.value = true
  try {
    const response: any = await chatAPI.getSystemPromptsByGroup()
    if (response && response.success && response.groups) {
      enhancedRoleGroups.value = response.groups

      // 如果还没有激活的分组或角色，自动选择第一个
      if (!activeEnhancedGroup.value && Object.keys(enhancedRoleGroups.value).length > 0) {
        const firstGroup = Object.keys(enhancedRoleGroups.value)[0]
        activeEnhancedGroup.value = firstGroup

        // 选择该分组的第一个角色
        if (enhancedRoleGroups.value[firstGroup] && enhancedRoleGroups.value[firstGroup].length > 0) {
          selectedEnhancedRole.value = enhancedRoleGroups.value[firstGroup][0].role_name

          // 不再应用所选角色的内容到systemPrompt，因为会在发送请求时根据enhancedRoleEnabled状态来决定使用哪个内容
          // 现在只需更新选择状态，具体的内容使用延迟到请求构建时
        }
      }
    } else {
      console.error('获取增强角色数据失败:', response?.msg)
    }
  } catch (error) {
    console.error('加载增强角色时出错:', error)
  } finally {
    loadingEnhancedRoles.value = false
  }
}

// 处理增强角色启用状态切换
const handleEnhancedRoleToggle = (enabled: boolean) => {
  enhancedRoleEnabled.value = enabled
  localStorage.setItem('enhancedRoleEnabled', JSON.stringify(enabled))

  if (enabled) {
    // 启用增强角色时，只需要更新状态，不在这里修改systemPrompt
    // systemPrompt值将在发送请求时根据enhancedRoleEnabled状态来决定使用哪个内容
    // 加载数据并准备使用第一个角色
    loadEnhancedRoles()
  } else {
    // 禁用增强角色时，也不需要恢复原来的预设角色内容到systemPrompt
    // 因为现在是在请求时根据状态来决定使用哪个内容
  }
}

// 处理增强角色分组切换
const handleGroupChange = (groupName: string) => {
  activeEnhancedGroup.value = groupName
  localStorage.setItem('activeEnhancedGroup', groupName)

  // 选择该分组的第一个角色
  if (enhancedRoleGroups.value[groupName] && enhancedRoleGroups.value[groupName].length > 0) {
    selectedEnhancedRole.value = enhancedRoleGroups.value[groupName][0].role_name

    // 不再应用所选角色的内容到systemPrompt，因为会在发送请求时根据enhancedRoleEnabled状态来决定使用哪个内容
    // 现在只需更新选择状态，具体的内容使用延迟到请求构建时

    // 保存到localStorage
    localStorage.setItem('selectedEnhancedRole', selectedEnhancedRole.value)
  }
}

// 处理增强角色选择
const handleEnhancedRoleSelect = (roleName: string) => {
  selectedEnhancedRole.value = roleName
  localStorage.setItem('selectedEnhancedRole', roleName)

  // 不再应用所选角色的内容到systemPrompt，因为会在发送请求时根据enhancedRoleEnabled状态来决定使用哪个内容
  // 现在只需更新选择状态，具体的内容使用延迟到请求构建时
}

// 重构：不再主动将增强角色内容应用到systemPrompt
// 根据enhancedRoleEnabled状态在发送请求时决定使用哪个内容作为system角色的内容
// const applyEnhancedRoleContent = () => {
//   const currentRoleContent = currentEnhancedRoleContent.value
//   if (currentRoleContent) {
//     systemPrompt.value = currentRoleContent
//   }
// }

// 重命名角色函数
const renameRole = (roleId: string) => {
  const role = rolePresets.value.find(r => r.id === roleId)
  if (role) {
    const newName = prompt('请输入新的角色名称:', role.name)
    if (newName && newName.trim()) {
      role.name = newName.trim()
      // 如果当前角色被重命名，则更新本地存储
      if (activeRoleId.value === roleId) {
        localStorage.setItem('activeRoleId', roleId)
      }
      saveCustomRoles() // 保存自定义角色
    }
  }
}

// 处理厂商选择变化
const handleProviderChange = (value: string) => {
  // 当厂商改变时，清空已选择的模型
  modelValue.value = ''
  // 如果值被清空，也清空selectedModel
  if (!value) {
    selectedModel.value = ''
  }
}

// 处理模型选择变化
const handleModelChange = (value: string) => {
  // 更新主selectedModel变量
  selectedModel.value = value

  // 更新当前模型描述
  const selectedModelObj = models.value.find(model => model.value === value)
  currentModelDesc.value = selectedModelObj?.model_desc || ''
}

// 更新厂商列表
const updateProviders = () => {
  // 从模型列表中提取厂商名称（基于模型值中的前缀）
  const uniqueProviders = new Set<string>()

  models.value.forEach(model => {
    const lowerValue = model.value.toLowerCase()

    // 按优先级匹配厂商前缀
    if (lowerValue.includes('gpt')) {
      uniqueProviders.add('gpt')
    } else if (lowerValue.includes('gemini')) {
      uniqueProviders.add('gemini')
    } else if (lowerValue.includes('qwen')) {
      uniqueProviders.add('qwen')
    } else if (lowerValue.includes('nano-banana')) {
      uniqueProviders.add('nano-banana')
    } else if (lowerValue.includes('deepseek')) {
      uniqueProviders.add('deepseek')
    } else {
      // 如果没有匹配到预定义的厂商，使用第一个单词作为厂商
      const firstPart = model.value.split('-')[0]
      if (firstPart && firstPart.length > 1) {
        uniqueProviders.add(firstPart)
      }
    }
  })

  providers.value = Array.from(uniqueProviders).sort()
}

// TODO(human): 改进供应商识别算法，使它能更准确地匹配模型名称和供应商
// 目前的算法只是简单的关键词匹配，可能无法正确处理所有模型名称格式
// 你可以考虑以下方案：
// 1. 维护一个更详细的供应商-模型映射表
// 2. 使用更复杂的正则表达式匹配规则
// 3. 根据API返回的分组信息来确定供应商

// 删除角色函数
const deleteRole = (roleId: string) => {
  // 只允许删除自定义角色，不允许删除预设角色
  if (['default', 'programmer', 'translator', 'writer'].includes(roleId)) {
    ElMessage.warning('不能删除预设角色')
    return
  }

  const roleIndex = rolePresets.value.findIndex(r => r.id === roleId)
  if (roleIndex !== -1) {
    const roleName = rolePresets.value[roleIndex].name
    ElMessageBox.confirm(
      `确定要删除角色 "${roleName}" 吗？`,
      '删除角色',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    ).then(() => {
      rolePresets.value.splice(roleIndex, 1)
      saveCustomRoles() // 保存自定义角色

      // 如果删除的是当前选中的角色，则切换到默认角色
      if (activeRoleId.value === roleId) {
        const defaultRole = rolePresets.value.find(r => r.id === 'default')
        if (defaultRole) {
          switchRole(defaultRole)
        }
      }

      ElMessage.success('角色已删除')
    }).catch(() => {
      // 用户取消删除
    })
  }
}

// 处理角色操作
const handleRoleAction = (command: string, roleId: string) => {
  if (command === 'rename') {
    renameRole(roleId)
  } else if (command === 'delete') {
    deleteRole(roleId)
  }
}

// 添加级联选择器状态变量
const cascaderValue = ref<string[]>([])
const cascaderOptions = ref<any[]>([])

// 将原始模型列表转换为级联选项
const convertModelsToCascaderOptions = (modelList: Array<{ label: string, value: string }>) => {
  // 使用真实获取的分组数据
  if (Object.keys(groupedModels.value).length > 0) {
    // 如果已有分组数据，直接使用
    return Object.entries(groupedModels.value)
      .filter(([_, models]) => models.length > 0) // 只包含有模型的分组
      .map(([groupName, models]) => ({
        value: groupName,
        label: groupName.charAt(0).toUpperCase() + groupName.slice(1), // 首字母大写
        children: (models as any[]).map(model => ({
          value: model.id,
          label: model.label || model.id
        }))
      }));
  } else {
    // 回退到按关键词匹配的方式
    const prefixes = ['gpt', 'gemini', 'qwen', 'nano-banana', 'deepseek'];

    // 按前缀分组模型
    const grouped: Record<string, { label: string, value: string }[]> = {};

    // 初始化分组
    prefixes.forEach(prefix => {
      grouped[prefix] = [];
    });

    // 分类模型
    modelList.forEach(model => {
      const lowerValue = model.value.toLowerCase();
      let matched = false;

      // 按优先级匹配前缀
      for (const prefix of prefixes) {
        if (lowerValue.includes(prefix)) {
          grouped[prefix].push(model);
          matched = true;
          break;
        }
      }

      // 如果没有匹配到任何前缀，放入"其他"分组
      if (!matched) {
        if (!grouped['other']) {
          grouped['other'] = [];
        }
        grouped['other'].push(model);
      }
    });

    // 生成级联选项
    return Object.entries(grouped)
      .filter(([_, models]) => models.length > 0) // 只包含有模型的分组
      .map(([groupName, models]) => {
        // 显示友好名称
        let displayName = groupName;
        if (groupName === 'other') displayName = '其他';

        return {
          value: groupName,
          label: displayName.charAt(0).toUpperCase() + displayName.slice(1), // 首字母大写
          children: models.map(model => ({
            value: model.value,
            label: model.label || model.value
          }))
        }
      });
  }
}

// 监听模型列表变化，自动生成级联选项
watch(models, (newModels) => {
  if (newModels && newModels.length > 0) {
    cascaderOptions.value = convertModelsToCascaderOptions(newModels)
    // 新增：同步 cascaderValue
    if (selectedModel.value) {
      for (const group of cascaderOptions.value) {
        const modelOption = group.children.find((child: any) => child.value === selectedModel.value)
        if (modelOption) {
          cascaderValue.value = [group.value, modelOption.value]
          break
        }
      }
    }
  }
}, { deep: true })

// 处理级联选择器变化
const handleCascaderChange = (value: string[]) => {
  if (value && value.length === 2) {
    // value[0] 是分组名, value[1] 是模型值
    selectedModel.value = value[1]
  } else {
    selectedModel.value = ''
  }
}

// 用于测试 LaTeX 渲染的函数（开发用途）
const testLatexRendering = () => {
  const testMessage = {
    type: 'ai' as const,
    content: '这是一个包含数学公式的示例：$$y = X\\beta + \\epsilon$$ 和内联公式 $E=mc^2$。',
    time: getCurrentTime()
  };
  messages.push(testMessage);
  nextTick(() => {
    scrollToBottom();
  });
}

// 监听selectedModel变化，同步更新级联选择器
watch(selectedModel, (newValue) => {
  if (newValue) {
    // 找到对应的分组和模型
    for (const group of cascaderOptions.value) {
      const modelOption = group.children.find((child: any) => child.value === newValue)
      if (modelOption) {
        cascaderValue.value = [group.value, modelOption.value]
        return
      }
    }
  } else {
    cascaderValue.value = []
  }
})

const messages = reactive<Array<{
  type: 'user' | 'ai'
  content: string
  time: string
  file?: File
  isError?: boolean  // 添加错误状态
  finishReason?: 'stop' | 'length' | 'content_filter' | 'tool_calls'  // 新增
  isTruncated?: boolean  // 新增
}>>([
  {
    type: 'ai',
    content: '您好！我是AI助手，有什么可以帮助您的吗？',
    time: getCurrentTime()
  }
])

// 自定义 renderer 用于处理数学公式
const mathRenderer = {
  inlineMath: (math: string) => {
    try {
      return katex.renderToString(math, {
        throwOnError: false,
        displayMode: false
      });
    } catch (error) {
      console.warn('KaTeX rendering error:', error);
      // 如果渲染失败，返回原始公式文本
      return `$${math}$`;
    }
  },
  displayMath: (math: string) => {
    try {
      return katex.renderToString(math, {
        throwOnError: false,
        displayMode: true
      });
    } catch (error) {
      console.warn('KaTeX rendering error:', error);
      // 如果渲染失败，返回原始公式文本
      return `$$${math}$$`;
    }
  }
};

// 解析包含数学公式的Markdown内容
const renderMarkdownWithMath = (content: string) => {
  // 保存代码块内容，防止其中的数学公式被错误处理
  const codeBlockPlaceholders: string[] = [];
  const inlineCodePlaceholders: string[] = [];

  // 提取并替换代码块（```code```）
  let processedContent = content.replace(/```[\s\S]*?```/g, (match) => {
    codeBlockPlaceholders.push(match);
    return `__CODE_BLOCK_PLACEHOLDER_${codeBlockPlaceholders.length - 1}__`;
  });

  // 提取并替换行内代码（`code`）
  processedContent = processedContent.replace(/`[^`]*`/g, (match) => {
    inlineCodePlaceholders.push(match);
    return `__INLINE_CODE_PLACEHOLDER_${inlineCodePlaceholders.length - 1}__`;
  });

  // 首先处理显示数学公式 $$...$$（只在非代码块内容中处理）
  processedContent = processedContent.replace(/\$\$(.*?)\$\$/gs, (match, math) => {
    return mathRenderer.displayMath(math.trim());
  });

  // 然后处理内联数学公式 $...$（只在非代码块内容中处理）
  processedContent = processedContent.replace(/\$([^\$]+)\$/g, (match, math) => {
    // 确保 $ 不是紧跟在字母或数字后面的（避免将价格等误认为数学公式）
    // 检查匹配项之前是否有字母或数字，或者检查是否为常见价格格式
    const prevChar = content[content.indexOf(match) - 1];
    const pricePattern = /^\$\d+(\.\d{1,2})?\s*$/; // 匹配 $数字 格式，如 $50 或 $12.34

    if (match.startsWith('\\$') || (prevChar && /\w/.test(prevChar)) || pricePattern.test(match + ' ')) {
      return match; // 如果是类似 $50 的格式或前面紧接字母/数字，不处理
    }
    return mathRenderer.inlineMath(math.trim());
  });

  // 将代码块内容还原回去
  for (let i = 0; i < codeBlockPlaceholders.length; i++) {
    processedContent = processedContent.replace(
      `__CODE_BLOCK_PLACEHOLDER_${i}__`,
      codeBlockPlaceholders[i]
    );
  }

  // 将行内代码内容还原回去
  for (let i = 0; i < inlineCodePlaceholders.length; i++) {
    processedContent = processedContent.replace(
      `__INLINE_CODE_PLACEHOLDER_${i}__`,
      inlineCodePlaceholders[i]
    );
  }

  // 解析 Markdown
  const parsedContent = marked.parse(processedContent || '');
  let result = typeof parsedContent === 'string' ? parsedContent.trim() : parsedContent;

  // 为Markdown生成的图片添加CSS类
  result = result.replace(/<img\s+([^>]*?)>/gi, '<img $1 class="attachment-preview" />');

  return result;
}

const renderMarkdown = (content: string) => {
  return renderMarkdownWithMath(content);
}

function getCurrentTime() {
  return new Date().toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit'
  })
}

const handleFileChange = async (file: any) => {
  try {
    // 检查是否为MD文件，如果是则重命名为TXT文件
    let fileToUpload = file.raw;
    if (file.raw.type === 'text/markdown' || file.name.toLowerCase().endsWith('.md')) {
      // 读取MD文件内容并创建新的TXT文件
      const textContent = await file.raw.text();
      const txtFileName = file.name.replace(/\.md$/, '.txt');
      fileToUpload = new File([textContent], txtFileName, { type: 'text/plain' });
      ElMessage.info(`MD文件已转换为TXT格式: ${txtFileName}`)
    }

    // 上传文件到服务器
    const response = await fileAPI.upload(fileToUpload)
    if (response && response.content) {
      // 文件上传成功，将URL添加到当前消息中
      uploadedFile.value = fileToUpload
      // 如果后端返回的content是相对路径或缺少host，则补充完整URL
      let fullUrl = response.content
      if (response.content.startsWith(':')) {
        // 如果返回以冒号开头（如 :4567/download/xxx.png），则添加当前页面的protocol和host
        fullUrl = window.location.protocol + '//' + window.location.host + response.content
      } else if (response.content.startsWith('/')) {
        // 如果返回以斜杠开头（如 /download/xxx.png），则添加当前页面的protocol和host
        fullUrl = window.location.protocol + '//' + window.location.host + response.content
      }
      // 在输入框中插入文件URL，使用特殊格式以支持Gemini模型
      inputMessage.value += `\n[FILE_URL:${fullUrl}]`
      ElMessage.success(`文件 "${fileToUpload.name}" 已上传`)
    } else {
      throw new Error(response.msg || '文件上传失败')
    }
  } catch (error: any) {
    console.error('文件上传错误:', error)
    let errorMessage = '文件上传失败'
    if (error.response?.data?.msg) {
      errorMessage = error.response.data.msg
    }
    ElMessage.error(errorMessage)
  }
}

const clearFile = () => {
  uploadedFile.value = null
  if (uploadRef.value) {
    uploadRef.value.clearFiles()
  }
}

const sendMessage = async () => {
  if (!inputMessage.value.trim()) return
  if (!selectedModel.value) {
    ElMessage.warning('请先选择一个模型')
    return
  }

  // TODO(human): 在发送新请求前，自动清除异常类的消息（包含重试或继续输出按钮的消息），避免将它们再次发送到后端
  // 实现逻辑应该是遍历当前消息数组，移除所有带有 isError 或 isTruncated 标记的消息，以及内容为空的AI消息
  // 这样可以确保新请求不会携带错误或截断的消息作为上下文

  // 清除异常类的消息（包含重试或继续输出按钮的消息）
  const welcomeMessage = '您好！我是AI助手，有什么可以帮助您的吗？'
  const normalMessages = messages.filter(msg => {
    // 保留欢迎消息
    if (msg.type === 'ai' && msg.content === welcomeMessage) {
      return true
    }
    // 过滤掉带有错误标记的消息
    if (msg.isError) {
      return false
    }
    // 过滤掉内容为空的AI消息（这些通常是有重新提问按钮的消息）
    if (msg.type === 'ai' && msg.content === '') {
      return false
    }
    // 过滤掉带有截断标记的消息
    if (msg.isTruncated) {
      return false
    }
    return true
  })

  // 如果消息数组被过滤，则替换原数组
  if (normalMessages.length !== messages.length) {
    // 保留正常的消息
    messages.splice(0, messages.length, ...normalMessages)
  }

  // 检查是否是图像生成模型
  const isImageModel = selectedModel.value && (selectedModel.value.toLowerCase().includes('dall') || selectedModel.value.toLowerCase().includes('image'));

  const userMessage = {
    type: 'user' as const,
    content: inputMessage.value,
    time: getCurrentTime(),
    file: uploadedFile.value || undefined
  }

  // 在构建对话数组之前先保存当前的上下文消息
  const contextSnapshot = [...messages]; // 创建当前消息快照用于构建上下文

  // 添加用户消息到数组
  messages.push(userMessage)

  // 如果当前没有设置标题，则将用户输入作为对话标题（只在第一次发送时）
  if (!dialogTitle.value.trim()) {
    // 截取前50个字符作为标题
    dialogTitle.value = inputMessage.value.length > 50
      ? inputMessage.value.substring(0, 50) + '...'
      : inputMessage.value
  }

  inputMessage.value = ''
  const currentFile = uploadedFile.value
  uploadedFile.value = null
  if (uploadRef.value) {
    uploadRef.value.clearFiles()
  }

  isLoading.value = true

  // 滚动到底部
  await nextTick()
  scrollToBottom()

  try {
    // 根据模型类型调用相应的API
    if (isImageModel) {
      // 图像生成模型仍使用普通API
      const aiResponse: any = await chatAPI.sendImageGeneration(selectedModel.value, userMessage.content, contextCount.value > 0 ? 'multi' : 'single', buildDialogArrayFromSnapshot(contextSnapshot, userMessage.content), dialogTitle.value)

      // 处理响应
      let responseContent = ''
      if (typeof aiResponse === 'object' && aiResponse.desc) {
        responseContent = aiResponse.desc
        // 如果是图片生成，添加图片URL
        if (aiResponse.url) {
          responseContent += `\n图片链接: ${window.location.origin}${aiResponse.url}`
        }
      } else {
        responseContent = JSON.stringify(aiResponse)
      }

      messages.push({
        type: 'ai',
        content: responseContent,
        time: getCurrentTime()
      })
    } else {
      // 根据开关决定使用流式还是非流式API
      if (streamEnabled.value) {
        // 使用流式API
        const aiMessageIndex = messages.length
        messages.push({
          type: 'ai',
          content: '',  // 初始内容为空
          time: getCurrentTime()
        })

        // 使用之前保存的上下文快照构建对话数组，避免因异步操作造成的混乱
        const dialogArray = buildDialogArrayFromSnapshot(contextSnapshot, userMessage.content)

        await chatAPI.sendChatStream(
          selectedModel.value,
          userMessage.content,
          (content, done, finishReason) => {
            messages[aiMessageIndex].content += content
            if (done) {
              isLoading.value = false
              if (finishReason === 'length') {
                messages[aiMessageIndex].finishReason = 'length'
                messages[aiMessageIndex].isTruncated = true
              }
              // 如果内容仍然为空，说明出现了问题
              else if (messages[aiMessageIndex].content === '') {
                messages[aiMessageIndex].isError = true
              }
            }
            // 只在用户位于底部时才滚动
            nextTick(() => {
              if (isScrolledToBottom.value) {
                scrollToBottom()
              }
            })
          },
          contextCount.value > 0 ? 'multi' : 'single',
          dialogArray,
          dialogTitle.value,  // 添加dialogTitle参数
          Math.round(maxResponseChars.value * 1.2 + 30) // 添加最大回复tokens参数（字数×2）
        )
      } else {
        // 使用非流式API
        const aiMessageIndex = messages.length
        messages.push({
          type: 'ai',
          content: '',  // 初始内容为空
          time: getCurrentTime()
        })

        // 使用之前保存的上下文快照构建对话数组
        const dialogArray = buildDialogArrayFromSnapshot(contextSnapshot, userMessage.content)

        const response: any = await chatAPI.sendChat(
          selectedModel.value,
          userMessage.content,
          contextCount.value > 0 ? 'multi' : 'single',
          dialogArray,
          dialogTitle.value,
          Math.round(maxResponseChars.value * 2.4) // 添加最大回复tokens参数（字数×2）
        )

        // 更新AI消息内容
        messages[aiMessageIndex].content = response.content
        if (response.finish_reason === 'length') {
          messages[aiMessageIndex].finishReason = response.finish_reason as 'length'
          messages[aiMessageIndex].isTruncated = true
        }

        isLoading.value = false
        // 滚动到底部
        nextTick(() => {
          if (isScrolledToBottom.value) {
            scrollToBottom()
          }
        })
      }
    }
  } catch (error: any) {
    console.error('API Error:', error)
    let errorMessage = '获取AI回复失败，请重试'
    if (error.response) {
      errorMessage = `错误: ${error.response.data?.msg || error.response.statusText}`
    } else if (error.request) {
      errorMessage = '网络请求失败，请检查后端服务是否正常运行'
    } else if (error.message) {
      // 更新判断条件，匹配后端返回的实际错误消息内容
      if (error.message.includes('API错误') || error.message.includes('API请求失败') ||
          error.message.includes('网段') || error.message.includes('白名单') ||
          error.message.includes('IP') || error.message.includes('ip')) {
        // 特别处理API错误信息，这通常来自SSE流中的错误消息
        errorMessage = error.message
      } else {
        // 其他类型的错误消息也直接使用
        errorMessage = error.message
      }
    }

    // 添加错误AI消息，带有重试功能
    messages.push({
      type: 'ai',
      content: errorMessage,
      time: getCurrentTime(),
      isError: true  // 添加错误状态
    })
  } finally {
    isLoading.value = false
    await nextTick()
    scrollToBottom()

    // 刷新对话历史记录
    await loadDialogHistory()
  }
}

// 获取用量信息
const fetchUsage = async () => {
  if (showUsagePopover.value) {
    // 如果弹窗已经打开，不再重复请求
    return
  }

  loadingUsage.value = true
  usageError.value = ''

  try {
    const response: any = await chatAPI.getUsage()
    if (response && response.success) {
      usageData.value = response.data
    } else {
      usageError.value = response?.msg || '获取用量信息失败'
    }
  } catch (error: any) {
    console.error('获取用量错误:', error)
    usageError.value = error.response?.data?.msg || error.message || '获取用量信息失败'
  } finally {
    loadingUsage.value = false
  }
}

// 加载对话历史
const loadDialogHistory = async () => {
  if (!authStore.user) {
    ElMessage.warning('请先登录')
    return
  }

  loadingHistory.value = true
  try {
    const response: any = await chatAPI.getDialogHistory()
    if (response && response.content) {
      dialogHistory.value = response.content
      // ElMessage.success(`加载了 ${response.content.length} 条历史对话`)
    } else {
      dialogHistory.value = []
      ElMessage.info('暂无历史对话')
    }
  } catch (error: any) {
    console.error('加载对话历史错误:', error)
    ElMessage.error('加载对话历史失败')
  } finally {
    loadingHistory.value = false
  }
}

// 清空当前会话
const clearCurrentSession = () => {
  messages.splice(0, messages.length)
  messages.push({
    type: 'ai',
    content: '您好！我是AI助手，有什么可以帮助您的吗？',
    time: getCurrentTime()
  })
  // 清空对话标题和当前对话ID
  dialogTitle.value = ''
  currentDialogId.value = null
  ElMessage.success('已开启新会话')
}

// 加载特定对话内容
const loadDialogContent = async (dialogId: number) => {
  if (!authStore.user) {
    ElMessage.warning('请先登录')
    return
  }

  try {
    const response: any = await chatAPI.getDialogContent(dialogId)
    if (response && response.content) {
      // 清空当前消息并加载对话内容
      messages.splice(0, messages.length)

      // 根据对话类型确定如何解析内容
      const context = response.content.context
      if (Array.isArray(context)) {
        context.forEach((item: any) => {
          if (item.role === 'system') {
            // 不再覆盖本地角色设定，直接跳过system消息
            return
          }
          if (item.role === 'user') {
            messages.push({
              type: 'user',
              content: item.content || item.desc || JSON.stringify(item),
              time: getCurrentTime()
            })
          } else if (item.role === 'assistant') {
            messages.push({
              type: 'ai',
              content: item.content || item.desc || JSON.stringify(item),
              time: getCurrentTime()
            })
          }
        })
      }

      // 设置当前对话ID和标题
      currentDialogId.value = dialogId
      const dialogItem = dialogHistory.value.find(d => d.id === dialogId)
      if (dialogItem) {
        dialogTitle.value = dialogItem.dialog_name

        // 根据历史记录中的modelname更新模型选择框
        if (dialogItem.modelname) {
          selectedModel.value = dialogItem.modelname

          // 更新提供商和模型选择器
          const selectedModelInfo = models.value.find(model => model.value === dialogItem.modelname)
          if (selectedModelInfo) {
            const lowerValue = selectedModelInfo.value.toLowerCase()
            if (lowerValue.includes('gpt')) {
              providerValue.value = 'gpt'
            } else if (lowerValue.includes('gemini')) {
              providerValue.value = 'gemini'
            } else if (lowerValue.includes('qwen')) {
              providerValue.value = 'qwen'
            } else if (lowerValue.includes('nano-banana')) {
              providerValue.value = 'nano-banana'
            } else if (lowerValue.includes('deepseek')) {
              providerValue.value = 'deepseek'
            } else {
              const firstPart = selectedModelInfo.value.split('-')[0]
              if (firstPart && firstPart.length > 1) {
                providerValue.value = firstPart
              }
            }
            modelValue.value = dialogItem.modelname

            // 更新当前模型描述
            currentModelDesc.value = selectedModelInfo.model_desc || ''
          }
        }
      }

      ElMessage.success('对话加载成功')
    }
  } catch (error: any) {
    console.error('加载对话内容错误:', error)
    ElMessage.error('加载对话内容失败')
  }
}

// 当标题输入框失去焦点时的处理
const handleTitleBlur = () => {
  // 在这里可以进行额外的验证或处理
  // 移除保存到localStorage的功能，这样标题不会被持久化
  // if (dialogTitle.value.trim()) {
  //   localStorage.setItem('dialogTitle', dialogTitle.value.trim())
  // }
}

// 当用户点击更新标题按钮时
const updateDialogTitle = async () => {
  if (!currentDialogId.value) {
    ElMessage.warning('当前没有打开的对话，无法更新标题')
    return
  }

  if (!dialogTitle.value.trim()) {
    ElMessage.warning('对话标题不能为空')
    return
  }

  try {
    const response: any = await chatAPI.updateDialogTitle(currentDialogId.value, dialogTitle.value.trim())
    if (response && response.success) {
      ElMessage.success('对话标题更新成功')

      // 更新对话历史列表中的标题
      const dialogItem = dialogHistory.value.find(d => d.id === currentDialogId.value)
      if (dialogItem) {
        dialogItem.dialog_name = dialogTitle.value.trim()
      }
    } else {
      ElMessage.error(response.msg || '更新对话标题失败')
    }
  } catch (error: any) {
    console.error('更新对话标题错误:', error)
    ElMessage.error('更新对话标题失败')
  }
}

// 处理字体大小变化
const handleFontSizeChange = (size: string) => {
  // 可以在这里执行一些额外的逻辑，如果需要
  fontSize.value = size
}

// 导出对话截屏（长截图）
const exportConversationScreenshot = async () => {
  try {
    let html2canvas: any;
    try {
      // 尝试动态导入 html2canvas
      const html2canvasModule = await import('html2canvas');
      html2canvas = html2canvasModule.default || html2canvasModule;
    } catch (e) {
      // 如果没有安装，提示用户安装
      ElMessage.warning('截图功能需要安装 html2canvas 库：npm install html2canvas');
      return;
    }

    const messagesContainer = document.querySelector('.messages-container') as HTMLElement;
    if (!messagesContainer) {
      ElMessage.error('无法找到对话容器');
      return;
    }

    // 根据当前主题确定背景色
    const isDarkTheme = document.body.classList.contains('dark-theme');
    const bgColor = isDarkTheme ? '#1a1a1a' : '#f9f7f0';

    // 创建一个临时的容器来存放完整的消息列表
    const tempContainer = document.createElement('div');
    tempContainer.className = 'messages-container-temp';
    tempContainer.style.position = 'absolute';
    tempContainer.style.left = '-9999px'; // 隐藏元素
    tempContainer.style.width = messagesContainer.clientWidth + 'px';
    tempContainer.style.backgroundColor = bgColor;
    tempContainer.style.padding = '20px';
    tempContainer.style.boxSizing = 'border-box';

    // 在顶部添加对话标题（如果存在）
    if (dialogTitle.value.trim()) {
      const titleElement = document.createElement('div');
      titleElement.style.textAlign = 'center';
      titleElement.style.fontSize = '24px';
      titleElement.style.fontWeight = 'bold';
      titleElement.style.marginBottom = '20px';
      titleElement.style.color = isDarkTheme ? '#ffffff' : '#333333';
      titleElement.textContent = dialogTitle.value;
      tempContainer.appendChild(titleElement);
    }

    // 复制消息内容到临时容器
    tempContainer.innerHTML += messagesContainer.innerHTML;

    // 将临时容器添加到文档中
    document.body.appendChild(tempContainer);

    // 生成截图
    const canvas = await html2canvas(tempContainer, {
      scale: 2, // 提高清晰度
      useCORS: true,
      allowTaint: true,
      backgroundColor: bgColor,
      width: tempContainer.scrollWidth,
      height: tempContainer.scrollHeight,
      scrollX: 0,
      scrollY: 0
    });

    // 移除临时容器
    document.body.removeChild(tempContainer);

    // 创建下载链接
    const link = document.createElement('a');
    link.download = `conversation_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.png`;
    link.href = canvas.toDataURL('image/png');
    link.click();

    ElMessage.success('对话截图已导出');
  } catch (error) {
    console.error('导出截图失败:', error);
    ElMessage.error('导出截图失败，请稍后重试');
  }
}

// 构建对话数组函数
const buildDialogArray = (currentMessage: string): Array<{role: string, content: string}> => {
  if (contextCount.value === 0) {
    return [{ role: 'user', content: currentMessage }]
  }

  const dialogArray: Array<{role: string, content: string}> = []
  // 获取有效消息（user 和 ai 类型），但排除初始欢迎消息和当前消息
  const welcomeMessage = '您好！我是AI助手，有什么可以帮助您的吗？'
  const validMessages = messages.filter(msg => (msg.type === 'user' || msg.type === 'ai') && msg.content !== welcomeMessage)

  // 获取要包含的上下文消息（排除当前用户消息）
  const contextMessages = validMessages.slice(0, -1) // 排除最后一条（当前用户消息）
  const messagesToInclude = contextMessages.slice(-contextCount.value) // 只取最新的几条

  for (const msg of messagesToInclude) {
    dialogArray.push({
      role: msg.type === 'user' ? 'user' : 'assistant',
      content: msg.content
    })
  }
  dialogArray.push({ role: 'user', content: currentMessage })
  return dialogArray
}

// 从消息快照构建对话数组函数
const buildDialogArrayFromSnapshot = (snapshot: any[], currentMessage: string): Array<{role: string, content: string}> => {
  const dialogArray: Array<{role: string, content: string}> = []

  // 如果有角色设定，添加到最前面
  // 根据enhancedRoleEnabled状态决定使用systemPrompt还是currentEnhancedRoleContent作为system角色的内容
  const systemContent = enhancedRoleEnabled.value ? currentEnhancedRoleContent.value : systemPrompt.value
  if (systemContent && systemContent.trim()) {
    dialogArray.push({ role: 'system', content: systemContent.trim() })
  }

  // 如果上下文数量为 0，只发送当前消息（但仍需包含 system 消息）
  if (contextCount.value === 0) {
    dialogArray.push({ role: 'user', content: currentMessage })
    return dialogArray
  }

  // 获取快照中的有效消息（user 和 ai 类型），但排除初始欢迎消息
  const welcomeMessage = '您好！我是AI助手，有什么可以帮助您的吗？'
  const validMessages = snapshot.filter((msg: any) => (msg.type === 'user' || msg.type === 'ai') && msg.content !== welcomeMessage)

  // 获取要包含的上下文消息
  const messagesToInclude = validMessages.slice(-contextCount.value) // 只取最新的几条

  for (const msg of messagesToInclude) {
    dialogArray.push({
      role: msg.type === 'user' ? 'user' : 'assistant',
      content: msg.content
    })
  }

  dialogArray.push({ role: 'user', content: currentMessage })
  return dialogArray
}

// 检测移动设备
const checkMobile = () => {
  const wasMobile = isMobile.value;
  isMobile.value = window.innerWidth < 768

  // 只在首次检测到移动设备或从桌面切换到移动设备时折叠侧边栏
  // 避免在移动端键盘弹出/隐藏时重复折叠侧边栏
  if (isMobile.value && !wasMobile) {
    sidebarCollapsed.value = true
  }
}

// 处理软键盘显示/隐藏
const handleResize = () => {
  // 检测是否为移动设备上的键盘变化
  const currentIsMobile = window.innerWidth < 768
  if (currentIsMobile) {
    // 使用屏幕高度变化来判断键盘是否弹出
    const screenHeight = window.screen.height
    const windowHeight = window.innerHeight

    // 如果窗口高度明显小于屏幕高度，很可能是因为键盘弹出了
    const likelyKeyboardVisible = screenHeight - windowHeight > 150

    if (likelyKeyboardVisible !== isKeyboardVisible.value) {
      isKeyboardVisible.value = likelyKeyboardVisible

      // 如果键盘弹出，延时滚动到底部确保输入框和按钮可见
      if (likelyKeyboardVisible) {
        setTimeout(() => {
          scrollToBottom()
        }, 300) // 给一点时间让键盘完全弹出
      }
    }
  }
}

const scrollToBottom = () => {
  if (messagesContainer.value && isScrolledToBottom.value) {
    // 只有在用户已经滚动到底部时才继续滚动
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

// 监听滚动事件，判断用户是否滚动到了底部
const handleScroll = () => {
  if (messagesContainer.value) {
    const { scrollTop, scrollHeight, clientHeight } = messagesContainer.value
    // 如果距离底部小于50像素，则认为是在底部
    isScrolledToBottom.value = scrollHeight - scrollTop - clientHeight < 50

    // 控制回到顶部按钮的显示：当滚动位置超过一屏时显示
    showBackToTop.value = scrollTop > clientHeight

    // 如果软键盘弹出，自动保持滚动到底部
    if (isKeyboardVisible.value) {
      scrollToBottom()
    }
  }
}

// 回到顶部函数
const scrollToTop = () => {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTo({
      top: 0,
      behavior: 'smooth'
    })
  }
}

// 处理键盘事件：根据用户偏好发送消息
const handleKeydown = (event: KeyboardEvent) => {
  if (sendPreference.value === 'ctrl_enter') {
    // 如果用户选择Ctrl+Enter发送
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
      event.preventDefault()
      sendMessage()
    }
    // 普通回车不阻止默认行为，允许换行
  } else if (sendPreference.value === 'enter') {
    // 如果用户选择Enter发送
    if (event.key === 'Enter' && !event.shiftKey && !event.ctrlKey && !event.altKey && !event.metaKey) {
      event.preventDefault()
      sendMessage()
    }
    // Shift+Enter 或其他组合键仍然允许换行
  }
}

// 检查当前消息是否正在流式接收中
const isStreaming = (index: number) => {
  // 如果是AI消息并且是当前正在加载的那条消息
  const message = messages[index];
  if (message.type === 'ai') {
    // 检查是否是最新的AI消息且当前处于加载状态
    const lastAiMessageIndex = messages.reduce((lastIndex, msg, idx) => {
      if (msg.type === 'ai') {
        return idx; // 返回最后一个AI消息的索引
      }
      return lastIndex;
    }, -1);
    return index === lastAiMessageIndex && isLoading.value;
  }
  return false;
}

// 将Markdown内容转换为纯文本格式，保留结构信息
const convertMarkdownToPlainText = (content: string) => {
  // 创建一个临时div来解析HTML
  const tempDiv = document.createElement('div');
  tempDiv.innerHTML = renderMarkdownWithMath(content);

  // 递归处理DOM节点，保留适当的格式
  const processNode = (node: Node): string => {
    let result = '';

    if (node.nodeType === Node.TEXT_NODE) {
      return node.textContent || '';
    }

    if (node.nodeType === Node.ELEMENT_NODE) {
      const element = node as HTMLElement;
      const tagName = element.tagName.toLowerCase();

      // 根据标签类型添加适当的格式化
      switch (tagName) {
        case 'h1':
        case 'h2':
        case 'h3':
        case 'h4':
        case 'h5':
        case 'h6':
          // 标题添加对应的#号
          result += '#'.repeat(parseInt(tagName.charAt(1))) + ' ';
          break;
        case 'li':
          // 列表项前添加项目符号
          result += '• ';
          break;
        case 'p':
          // 段落之间添加换行
          result += '\n';
          break;
        case 'br':
          result += '\n';
          break;
        case 'strong':
        case 'b':
          // 粗体不添加标记，只保留内容
          break;
        case 'em':
        case 'i':
          // 斜体不添加标记，只保留内容
          break;
        case 'code':
          // 代码块保留反引号
          if (element.parentElement?.tagName.toLowerCase() !== 'pre') {
            result += '`';
          }
          break;
        case 'pre':
          // 代码块前后添加三个反引号
          result += '```\n';
          break;
      }

      // 递归处理子节点
      for (let i = 0; i < element.childNodes.length; i++) {
        result += processNode(element.childNodes[i]);
      }

      // 添加闭合格式
      switch (tagName) {
        case 'pre':
          result += '\n```';
          break;
        case 'code':
          if (element.parentElement?.tagName.toLowerCase() !== 'pre') {
            result += '`';
          }
          break;
        case 'p':
          result += '\n';
          break;
      }
    }

    return result;
  };

  // 处理整个div的内容
  let plainText = '';
  for (let i = 0; i < tempDiv.childNodes.length; i++) {
    plainText += processNode(tempDiv.childNodes[i]);
  }

  // 清理多余的空白行
  plainText = plainText.replace(/\n{3,}/g, '\n\n').trim();

  return plainText;
};

// 复制消息内容到剪贴板
const copyMessageContent = async (content: string) => {
  try {
    // 转换为带有结构的纯文本
    const plainText = convertMarkdownToPlainText(content);
    await navigator.clipboard.writeText(plainText);
    ElMessage.success('内容已复制到剪贴板');
  } catch (err) {
    console.error('复制失败:', err);
    // 如果 navigator.clipboard 不可用，使用传统的 document.execCommand 方法
    try {
      const textArea = document.createElement('textarea');
      // 转换为带有结构的纯文本
      const plainText = convertMarkdownToPlainText(content);
      textArea.value = plainText;
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand('copy');
      document.body.removeChild(textArea);
      ElMessage.success('内容已复制到剪贴板');
    } catch (fallbackErr) {
      console.error('复制失败:', fallbackErr);
      ElMessage.error('复制失败，请手动选择内容');
    }
  }
}

// 删除指定的消息
const deleteMessage = (index: number) => {
  if (index >= 0 && index < messages.length) {
    // 检查是否是AI欢迎消息，如果是则不允许删除
    const welcomeMessage = '您好！我是AI助手，有什么可以帮助您的吗？';
    if (messages[index].content === welcomeMessage && messages[index].type === 'ai') {
      ElMessage.warning('无法删除欢迎消息');
      return;
    }

    messages.splice(index, 1);
    ElMessage.success('消息已删除');
  }
}

// 重试发送特定AI消息（重新发送该消息所属的上下文）
const retryMessage = async (index: number) => {
  if (index < 0 || index >= messages.length || messages[index].type !== 'ai') {
    return;
  }

  // 清除异常类的消息（包含重试或继续输出按钮的消息），但保留当前要重试的消息
  const welcomeMessage = '您好！我是AI助手，有什么可以帮助您的吗？'
  const currentMessageToRetry = messages[index]; // 保存当前要重试的消息
  const normalMessages = messages.filter((msg, msgIndex) => {
    // 保留欢迎消息
    if (msg.type === 'ai' && msg.content === welcomeMessage) {
      return true
    }
    // 保留当前要重试的消息
    if (msgIndex === index) {
      return true
    }
    // 过滤掉带有错误标记的消息
    if (msg.isError) {
      return false
    }
    // 过滤掉内容为空的AI消息（这些通常是有重新提问按钮的消息）
    if (msg.type === 'ai' && msg.content === '') {
      return false
    }
    // 过滤掉带有截断标记的消息
    if (msg.isTruncated) {
      return false
    }
    return true
  })

  // 如果消息数组被过滤，则替换原数组
  if (normalMessages.length !== messages.length) {
    // 保留正常的消息
    messages.splice(0, messages.length, ...normalMessages)
  }

  // 重新查找要重试的消息的新索引
  const newIndexOfRetryMessage = messages.indexOf(currentMessageToRetry);

  // 如果消息不存在（不应该发生），则返回
  if (newIndexOfRetryMessage === -1) {
    ElMessage.error('重试的消息不存在');
    return;
  }

  // 查找这个AI消息之前的用户消息
  let userMessageIndex = -1;
  for (let i = newIndexOfRetryMessage - 1; i >= 0; i--) {
    if (messages[i].type === 'user') {
      userMessageIndex = i;
      break;
    }
  }

  if (userMessageIndex === -1) {
    ElMessage.error('找不到对应的问题消息，无法重试');
    return;
  }

  const userMessage = messages[userMessageIndex];
  const aiMessage = messages[newIndexOfRetryMessage];

  // 移除错误或空的AI消息
  messages.splice(newIndexOfRetryMessage, 1);

  // 准备上下文信息（不包括当前错误的AI消息）
  const contextSnapshot = messages.slice(0, newIndexOfRetryMessage); // 获取到当前位置前的所有消息

  // 设置为加载状态
  isLoading.value = true;

  try {
    // 根据模型类型调用相应的API
    const isImageModel = selectedModel.value && (selectedModel.value.toLowerCase().includes('dall') || selectedModel.value.toLowerCase().includes('image'));

    if (isImageModel) {
      // 图像生成模型仍使用普通API
      const aiResponse: any = await chatAPI.sendImageGeneration(
        selectedModel.value,
        userMessage.content,
        contextCount.value > 0 ? 'multi' : 'single',
        buildDialogArrayFromSnapshot(contextSnapshot, userMessage.content),
        dialogTitle.value
      );

      // 处理响应
      let responseContent = '';
      if (typeof aiResponse === 'object' && aiResponse.desc) {
        responseContent = aiResponse.desc;
        // 如果是图片生成，添加图片URL
        if (aiResponse.url) {
          responseContent += `\n图片链接: ${window.location.origin}${aiResponse.url}`;
        }
      } else {
        responseContent = JSON.stringify(aiResponse);
      }

      // 添加新的AI消息（替代之前的错误消息）
      messages.splice(index, 0, {
        type: 'ai',
        content: responseContent,
        time: getCurrentTime()
      });
    } else {
      // 文本聊天使用流式API
      // 添加占位AI消息
      messages.splice(index, 0, {
        type: 'ai',
        content: '',  // 初始内容为空
        time: getCurrentTime()
      });

      // 使用上下文快照构建对话数组
      const dialogArray = buildDialogArrayFromSnapshot(contextSnapshot, userMessage.content);

      // 根据开关决定使用流式还是非流式API
      if (streamEnabled.value) {
        // 使用流式API
        await chatAPI.sendChatStream(
          selectedModel.value,
          userMessage.content,
          (content, done, finishReason) => {
            messages[index].content += content;
            if (done) {
              isLoading.value = false;
              if (finishReason === 'length') {
                messages[index].finishReason = 'length';
                messages[index].isTruncated = true;
              }
            }
            // 只在用户位于底部时才滚动
            nextTick(() => {
              if (isScrolledToBottom.value) {
                scrollToBottom();
              }
            });
          },
          contextCount.value > 0 ? 'multi' : 'single',
          dialogArray,
          dialogTitle.value,  // 添加dialogTitle参数
          Math.round(maxResponseChars.value * 1.2 + 30) // 添加最大回复tokens参数
        );
      } else {
        // 使用非流式API
        const response: any = await chatAPI.sendChat(
          selectedModel.value,
          userMessage.content,
          contextCount.value > 0 ? 'multi' : 'single',
          dialogArray,
          dialogTitle.value,
          Math.round(maxResponseChars.value * 2.4) // 添加最大回复tokens参数
        );

        // 更新AI消息内容
        messages[index].content = response.content;
        if (response.finish_reason === 'length') {
          messages[index].finishReason = response.finish_reason as 'length';
          messages[index].isTruncated = true;
        }

        isLoading.value = false;
        // 滚动到底部
        nextTick(() => {
          if (isScrolledToBottom.value) {
            scrollToBottom();
          }
        });
      }
    }

    ElMessage.success('消息重试成功');
  } catch (error: any) {
    console.error('重试API Error:', error);

    // 保留错误消息在AI消息中，而不是显示全局通知
    let errorMessage = '重试失败，请稍后再次重试';
    if (error.response) {
      errorMessage = `重试失败: ${error.response.data?.msg || error.response.statusText}`;
    } else if (error.request) {
      errorMessage = '网络请求失败，请检查后端服务是否正常运行';
    } else if (error.message) {
      if (error.message.includes('API错误') || error.message.includes('API请求失败') ||
          error.message.includes('网段') || error.message.includes('白名单') ||
          error.message.includes('IP') || error.message.includes('ip')) {
        errorMessage = `重试失败: ${error.message}`;
      } else {
        errorMessage = `重试失败: ${error.message}`;
      }
    }

    // 将错误信息更新到AI消息中
    messages.splice(index, 0, {
      type: 'ai',
      content: errorMessage,
      time: getCurrentTime(),
      isError: true  // 保持错误状态，用户仍可以再次重试
    });

    ElMessage.warning('重试失败，错误消息已更新到对话中');
  } finally {
    isLoading.value = false;
    await nextTick();
    scrollToBottom();
  }
}

// 进入编辑模式
const enterEditMode = () => {
  isEditMode.value = true
  selectedDialogs.value = []
}

// 退出编辑模式
const exitEditMode = () => {
  isEditMode.value = false
  selectedDialogs.value = []
}

// 显示 LaTeX 帮助对话框
const showLatexHelp = () => {
  showLatexHelpDialog.value = true
}

// 切换选择对话
const toggleSelectDialog = (dialogId: number) => {
  const index = selectedDialogs.value.indexOf(dialogId)
  if (index > -1) {
    selectedDialogs.value.splice(index, 1)
  } else {
    selectedDialogs.value.push(dialogId)
  }
}

// 确认单个删除
const confirmSingleDelete = async (dialogId: number) => {
  try {
    const response: any = await chatAPI.deleteDialogs([dialogId])
    if (response && response.success) {
      ElMessage.success(`对话删除成功，共删除 ${response.deleted_count} 条`)
      // 刷新对话历史
      await loadDialogHistory()
      // 如果当前会话被删除，清空聊天内容
      const dialogItem = dialogHistory.value.find(d => d.id === dialogId)
      if (dialogItem && dialogItem.dialog_name === dialogTitle.value) {
        clearCurrentSession()
      }
    } else {
      ElMessage.error('删除对话失败')
    }
  } catch (error: any) {
    console.error('删除对话错误:', error)
    ElMessage.error('删除对话失败')
  }
}

// 确认批量删除
const confirmBatchDelete = async () => {
  if (selectedDialogs.value.length === 0) {
    ElMessage.warning('请至少选择一个对话')
    return
  }

  try {
    const response: any = await chatAPI.deleteDialogs(selectedDialogs.value)
    if (response && response.success) {
      ElMessage.success(`批量删除成功，共删除 ${response.deleted_count} 条`)
      // 退出编辑模式
      exitEditMode()
      // 刷新对话历史
      await loadDialogHistory()
      // 如果当前会话被删除，清空聊天内容
      const currentDialog = dialogHistory.value.find(d => d.dialog_name === dialogTitle.value)
      if (currentDialog && selectedDialogs.value.includes(currentDialog.id)) {
        clearCurrentSession()
      }
    } else {
      ElMessage.error('批量删除失败')
    }
  } catch (error: any) {
    console.error('批量删除错误:', error)
    ElMessage.error('批量删除失败')
  }
}

// TODO(human): 考虑是否需要在某些情况下延迟刷新对话历史，以避免过于频繁的API请求
// 可以在这里添加防抖机制或根据响应时间决定是否立即刷新

const handleLogout = () => {
  authStore.logout()
  ElMessage.success('已退出登录')
  router.push('/login')
}

// 继续生成函数
const continueGeneration = async (index: number) => {
  if (contextCount.value < 3) {
    ElMessageBox.alert('请将携带历史消息数量设置为3或更高，以支持连续续写功能', '提示', {
      confirmButtonText: '确定',
    })
    return
  }

  if (isLoading.value) return

  const truncatedMessage = messages[index]
  if (!truncatedMessage || !truncatedMessage.isTruncated) return

  // 清除异常类的消息（包含重试或继续输出按钮的消息），但保留当前要继续生成的消息
  const welcomeMessage = '您好！我是AI助手，有什么可以帮助您的吗？'
  const currentMessageToContinue = messages[index]; // 保存当前要继续生成的消息
  const normalMessages = messages.filter((msg, msgIndex) => {
    // 保留欢迎消息
    if (msg.type === 'ai' && msg.content === welcomeMessage) {
      return true
    }
    // 保留当前要继续生成的消息
    if (msgIndex === index) {
      return true
    }
    // 过滤掉带有错误标记的消息
    if (msg.isError) {
      return false
    }
    // 过滤掉内容为空的AI消息（这些通常是有重新提问按钮的消息）
    if (msg.type === 'ai' && msg.content === '') {
      return false
    }
    // 过滤掉带有截断标记的消息（除了当前要处理的这条消息外）
    if (msg.isTruncated) {
      return false
    }
    return true
  })

  // 如果消息数组被过滤，则替换原数组
  if (normalMessages.length !== messages.length) {
    // 保留正常的消息
    messages.splice(0, messages.length, ...normalMessages)
  }

  // 重新查找要继续生成的消息的新索引
  const newIndexOfContinueMessage = messages.indexOf(currentMessageToContinue);

  // 如果消息不存在（不应该发生），则返回
  if (newIndexOfContinueMessage === -1) {
    ElMessage.error('继续生成的消息不存在');
    return;
  }

  // 创建一条新的AI消息用于继续生成
  const continueMessageIndex = messages.length
  messages.push({
    type: 'ai',
    content: '',
    time: getCurrentTime(),
    isTruncated: false // 新消息初始状态不是截断的
  })

  isLoading.value = true

  try {
    // 使用上一次截断的AI消息作为上下文，要求继续生成
    const userPrompt = "请继续生成未完成的内容，直接从上次中断的地方继续，不要重复已生成的内容。"

    // 构建包含截断回答的上下文，确保包含当前截断的消息
    const dialogArray = buildDialogArrayFromSnapshot(messages.slice(0, newIndexOfContinueMessage + 1), userPrompt)

    // 根据开关决定使用流式还是非流式API
    if (streamEnabled.value) {
      // 使用流式API
      await chatAPI.sendChatStream(
        selectedModel.value,
        userPrompt,
        (content, done, finishReason) => {
          messages[continueMessageIndex].content += content
          if (done) {
            isLoading.value = false
            if (finishReason === 'length') {
              messages[continueMessageIndex].finishReason = 'length'
              messages[continueMessageIndex].isTruncated = true
            }
          }
          // 只在用户位于底部时才滚动
          nextTick(() => {
            if (isScrolledToBottom.value) {
              scrollToBottom()
            }
          })
        },
        'multi', // 使用多轮对话模式以包含上下文
        dialogArray,
        dialogTitle.value,
        Math.round(maxResponseChars.value * 2.4) // 添加最大回复tokens参数
      )
    } else {
      // 使用非流式API
      const response: any = await chatAPI.sendChat(
        selectedModel.value,
        userPrompt,
        'multi', // 使用多轮对话模式以包含上下文
        dialogArray,
        dialogTitle.value,
        Math.round(maxResponseChars.value * 2.4) // 添加最大回复tokens参数
      )

      // 更新AI消息内容
      messages[continueMessageIndex].content = response.content
      if (response.finish_reason === 'length') {
        messages[continueMessageIndex].finishReason = response.finish_reason as 'length'
        messages[continueMessageIndex].isTruncated = true
      }

      isLoading.value = false
      // 滚动到底部
      nextTick(() => {
        if (isScrolledToBottom.value) {
          scrollToBottom()
        }
      })
    }
  } catch (error: any) {
    console.error('继续生成错误:', error)
    let errorMessage = '继续生成失败，请重试'
    if (error.response) {
      errorMessage = `错误: ${error.response.data?.msg || error.response.statusText}`
    } else if (error.request) {
      errorMessage = '网络请求失败，请检查后端服务是否正常运行'
    } else if (error.message) {
      errorMessage = error.message
    }

    // 标记当前消息为错误状态
    messages[continueMessageIndex].content = errorMessage
    messages[continueMessageIndex].isError = true
  } finally {
    isLoading.value = false
  }
}

// 组件挂载时加载模型列表
onMounted(async () => {
  // 检查版本更新并处理缓存
  VersionService.checkAndHandleVersionChange();

  // 首先加载自定义角色
  loadCustomRoles()

  try {
    // 优先尝试获取分组模型列表
    const response: any = await chatAPI.getGroupedModels()
    if (response && response.success && response.grouped_models) {
      // 保存分组模型数据
      groupedModels.value = response.grouped_models;

      // 将分组模型展平为普通列表
      models.value = [];
      for (const [prefix, modelList] of Object.entries(response.grouped_models)) {
        (modelList as Array<any>).forEach((model: any) => {
          models.value.push({
            label: `${prefix}: ${model.label || model.id}`,
            value: model.id,
            recommend: model.recommend || false,
            model_desc: model.model_desc || ''
          });
        });
      }
    } else {
      // 如果获取分组模型失败，回退到普通模型列表
      const normalResponse: any = await chatAPI.getModels();
      if (normalResponse && normalResponse.success && normalResponse.models) {
        models.value = normalResponse.models.map((model: any) => ({
          label: model.label,
          value: model.id,
          recommend: model.recommend || false,
          model_desc: model.model_desc || ''
        }));
      } else {
        console.error('获取模型列表失败:', response?.msg || normalResponse?.msg)
        // 设置默认模型列表作为备选
        models.value = [
          { label: 'GPT-4o mini', value: 'gpt-4o-mini', recommend: false, model_desc: '' },
          { label: 'GPT-4o', value: 'gpt-4o', recommend: false, model_desc: '' },
          { label: 'GPT-3.5-turbo', value: 'gpt-3.5-turbo', recommend: false, model_desc: '' }
        ]
      }
    }
  } catch (error) {
    console.error('加载模型列表时出错:', error)
    // 设置默认模型列表作为备选
    models.value = [
      { label: 'GPT-4o mini', value: 'gpt-4o-mini', recommend: false, model_desc: '' },
      { label: 'GPT-4o', value: 'gpt-4o', recommend: false, model_desc: '' },
      { label: 'GPT-3.5-turbo', value: 'gpt-3.5-turbo', recommend: false, model_desc: '' }
    ]
  }

  // 更新供应商列表
  updateProviders()

  // 如果有保存的模型选择，设置对应的供应商和模型
  if (selectedModel.value) {
    // 根据选择的模型值找到对应的供应商
    const selectedModelInfo = models.value.find(model => model.value === selectedModel.value)
    if (selectedModelInfo) {
      // 遍历模型值找出供应商
      const lowerValue = selectedModelInfo.value.toLowerCase()
      if (lowerValue.includes('gpt')) {
        providerValue.value = 'gpt'
      } else if (lowerValue.includes('gemini')) {
        providerValue.value = 'gemini'
      } else if (lowerValue.includes('qwen')) {
        providerValue.value = 'qwen'
      } else if (lowerValue.includes('nano-banana')) {
        providerValue.value = 'nano-banana'
      } else if (lowerValue.includes('deepseek')) {
        providerValue.value = 'deepseek'
      } else {
        // 如果没有匹配到预定义的供应商，使用第一个单词
        const firstPart = selectedModelInfo.value.split('-')[0]
        if (firstPart && firstPart.length > 1) {
          providerValue.value = firstPart
        }
      }
      modelValue.value = selectedModel.value

      // 设置当前模型描述
      currentModelDesc.value = selectedModelInfo.model_desc || ''
    }
  }

  // 注释掉从localStorage恢复对话标题的功能，实现每次刷新页面时标题栏都为空
  // const savedDialogTitle = localStorage.getItem('dialogTitle')
  // if (savedDialogTitle) {
  //   dialogTitle.value = savedDialogTitle
  // }

  // 从localStorage恢复发送键偏好
  const savedSendPreference = localStorage.getItem('sendPreference')
  if (savedSendPreference) {
    sendPreference.value = savedSendPreference
  }

  // 从localStorage恢复增强角色设置
  const savedEnhancedRoleEnabled = localStorage.getItem('enhancedRoleEnabled')
  if (savedEnhancedRoleEnabled) {
    enhancedRoleEnabled.value = JSON.parse(savedEnhancedRoleEnabled)
  }

  const savedActiveEnhancedGroup = localStorage.getItem('activeEnhancedGroup')
  if (savedActiveEnhancedGroup) {
    activeEnhancedGroup.value = savedActiveEnhancedGroup
  }

  const savedSelectedEnhancedRole = localStorage.getItem('selectedEnhancedRole')
  if (savedSelectedEnhancedRole) {
    selectedEnhancedRole.value = savedSelectedEnhancedRole
  }

  // 如果启用了增强角色，加载数据
  if (enhancedRoleEnabled.value) {
    await loadEnhancedRoles()
  }

  // 自动加载历史会话
  await loadDialogHistory()

  // 添加移动端检测和事件监听
  checkMobile()
  window.addEventListener('resize', checkMobile)

  // 添加resize事件监听器以处理软键盘弹出/收起
  window.addEventListener('resize', handleResize)

  // 添加滚动事件监听器
  if (messagesContainer.value) {
    messagesContainer.value.addEventListener('scroll', handleScroll)
    // 初始化滚动位置状态
    handleScroll()
  }

  // 初始化测试数学公式渲染（注释掉此行，仅用于开发测试）
  // testLatexRendering()
})

// 组件卸载时移除事件监听
onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
  window.removeEventListener('resize', handleResize) // 移除软键盘检测监听器
  // 移除滚动事件监听器
  if (messagesContainer.value) {
    messagesContainer.value.removeEventListener('scroll', handleScroll)
  }
})

/**
 * 异步检查文本溢出，确保DOM完全渲染后进行检测
 * @param element DOM元素
 * @returns Promise<boolean> 是否溢出
 */
const checkTextOverflowAsync = async (element: HTMLElement | null) => {
  if (!element) return false
  await nextTick()
  return element.scrollWidth > element.offsetWidth
}

/**
 * 判断是否应该显示tooltip
 * @param text 文本内容
 * @param type 类型（title 或 model）
 * @returns 是否显示tooltip
 */
const shouldShowTooltip = (text: string, type: 'title' | 'model') => {
  // 对于对话标题，如果长度超过30个字符则显示tooltip
  if (type === 'title') {
    return text && text.length > 20
  }
  // 对于模型名称，如果长度超过15个字符则显示tooltip
  else if (type === 'model') {
    return text && text.length > 12
  }
  return false
}

// TODO(human): 需要实现一个计算属性或方法来判断是否文本溢出，可能需要在 nextTick 后进行检测，以确保DOM完全渲染后再测量

/**
 * 检查文本元素是否发生溢出
 * @param element DOM元素
 * @returns 是否溢出
 */
const isTextOverflowing = (element: HTMLElement | null) => {
  if (!element) return false
  return element.scrollWidth > element.offsetWidth
}

</script>
<style>

</style>

