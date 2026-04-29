export interface FormData {
    isDarkTheme: boolean;
    currentDialogId: number | null;
    selectedModel: string;
    selectedModels: string[];
    selectedModelType: number;
    contextCount: number;
    sidebarCollapsed: boolean;
    maxResponseChars: number;
    isMobile: boolean;
    streamEnabled: boolean;
    systemPrompt: string;
    sendPreference: 'enter' | 'ctrl_enter' | undefined;
    dialogTitle: string;
    dialogHistory: any[];
    loadingHistory: boolean;
    isLoading: boolean;
    models: Array<{ group: string, label: string, value: string, recommend?: boolean, model_desc?: string, model_type?: number }>;
    groupedModels: Record<string, any[]>;
    providers: string[];
    providerValue: string;
    modelValue: string;
    currentModelDesc: string;
    enhancedRoleEnabled: boolean;
    enhancedRoleGroups: Record<string, any[]>;
    activeEnhancedGroup: string;
    selectedEnhancedRole: string;
    rolePresets: Array<{ id: string, name: string, prompt: string }>;
    activeRoleId: string;
    fontSize: string;
    chatApiMode: 'v1' | 'v2';
    runtimeChatMode: 'v1' | 'v2';
    v2Available: boolean;
    activeMasterId: number | null;
    v2MasterTitle: string;
    v2Masters: Array<any>;
    v2Children: Array<any>;
    v2Rounds: Array<any>;
    v2Cells: Array<any>;
    v2CellsMap: Record<string, any>;
    v2CellLoadingMap: Record<string, boolean>;
    v2ActiveChildId: number | null;
    systemPromptId?: number;  // 新增：选中的系统提示词 ID
    // 添加状态跟踪用户是否手动滚动离开了底部
    isScrolledToBottom: boolean;
  }
