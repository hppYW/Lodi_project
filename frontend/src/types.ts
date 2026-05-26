export type Theme = 'light' | 'dark';

export interface Source {
  doc: string;
  article: string;
  highlight?: boolean;
  quote?: string;
}

export type MessageRole = 'user' | 'bot' | 'typing';

export interface Message {
  id: string;
  role: MessageRole;
  text: string;
  timestamp: string;
  sources?: Source[];
  highlight?: boolean;
  searchingDocs?: string[];
}

export interface Chat {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  pinned: boolean;
  messages: Message[];
}

export interface AppState {
  chats: Chat[];
  activeChatId: string | null;
  theme: Theme;
  sidebarOpen: boolean;
}
