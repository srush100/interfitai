import React, { useEffect, useState, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TextInput,
  TouchableOpacity,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  Alert,
  Image,
  Modal,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useUserStore } from '../../src/store/userStore';
import { colors } from '../../src/theme/colors';
import api from '../../src/services/api';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  saved: boolean;
  created_at: string;
  title?: string;
}

interface SavedNote {
  id: string;
  title: string;
  content: string;
  created_at: string;
}

export default function AskAIScreen() {
  const { profile } = useUserStore();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'chat' | 'saved'>('chat');
  const scrollViewRef = useRef<ScrollView>(null);
  const [selectedNote, setSelectedNote] = useState<SavedNote | null>(null);
  const [showTitleModal, setShowTitleModal] = useState(false);
  const [pendingSaveMessage, setPendingSaveMessage] = useState<Message | null>(null);
  const [noteTitle, setNoteTitle] = useState('');
  const [savedNotes, setSavedNotes] = useState<SavedNote[]>([]);
  const [showRenameModal, setShowRenameModal] = useState(false);
  const [renameNote, setRenameNote] = useState<SavedNote | null>(null);
  const [newNoteName, setNewNoteName] = useState('');

  useEffect(() => {
    loadHistory();
    loadSavedNotes();
  }, [profile]);

  useEffect(() => {
    // Reload saved notes when switching to saved tab
    if (activeTab === 'saved') {
      loadSavedNotes();
    }
  }, [activeTab]);

  const loadHistory = async () => {
    if (!profile?.id) return;
    try {
      const response = await api.get(`/chat/history/${profile.id}?limit=50`);
      setMessages(response.data);
    } catch (error) {
      console.log('Error loading chat history:', error);
    } finally {
      setHistoryLoading(false);
    }
  };

  const loadSavedNotes = async () => {
    if (!profile?.id) return;
    try {
      const response = await api.get(`/chat/saved/${profile.id}`);
      const notes = response.data.map((m: any) => ({
        id: m.id,
        title: m.title || generateDefaultTitle(m.content),
        content: m.content,
        created_at: m.created_at,
      }));
      setSavedNotes(notes);
    } catch (error) {
      console.log('Error loading saved notes:', error);
    }
  };

  const chatMessages = messages;

  const sendMessage = async () => {
    if (!input.trim() || loading || !profile?.id) return;

    const userMessage = input.trim();
    setInput('');
    setLoading(true);

    // Add user message optimistically
    const tempUserMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: userMessage,
      saved: false,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    try {
      const response = await api.post('/chat', {
        user_id: profile.id,
        message: userMessage,
      });

      // Replace temp message with actual and add AI response
      setMessages((prev) => [
        ...prev.slice(0, -1),
        { ...tempUserMsg },
        response.data,
      ]);
    } catch (error) {
      Alert.alert('Error', 'Failed to get response. Please try again.');
      setMessages((prev) => prev.slice(0, -1));
    } finally {
      setLoading(false);
    }
  };

  const saveMessage = async (messageId: string, title: string) => {
    try {
      await api.post(`/chat/save/${messageId}`, null, {
        params: { title }
      });
      // Update message state
      const savedMsg = messages.find(m => m.id === messageId);
      setMessages((prev) =>
        prev.map((m) => (m.id === messageId ? { ...m, saved: true, title } : m))
      );
      // Add to saved notes
      if (savedMsg) {
        setSavedNotes((prev) => [...prev, {
          id: messageId,
          title,
          content: savedMsg.content,
          created_at: savedMsg.created_at
        }]);
      }
    } catch (error) {
      Alert.alert('Error', 'Failed to save message');
    }
  };

  const unsaveMessage = async (messageId: string) => {
    // Only update the visual state in chat, don't delete from saved notes
    try {
      setMessages((prev) =>
        prev.map((m) => (m.id === messageId ? { ...m, saved: false, title: undefined } : m))
      );
    } catch (error) {
      Alert.alert('Error', 'Failed to update message');
    }
  };

  const deleteNote = async (noteId: string) => {
    Alert.alert(
      'Delete Note',
      'Are you sure you want to permanently delete this saved note?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              await api.post(`/chat/unsave/${noteId}`);
              setSavedNotes((prev) => prev.filter((n) => n.id !== noteId));
              // Also update the message state if it exists
              setMessages((prev) =>
                prev.map((m) => (m.id === noteId ? { ...m, saved: false, title: undefined } : m))
              );
              if (selectedNote?.id === noteId) {
                setSelectedNote(null);
              }
            } catch (error) {
              Alert.alert('Error', 'Failed to delete note');
            }
          },
        },
      ]
    );
  };

  const openRenameModal = (note: SavedNote) => {
    setRenameNote(note);
    setNewNoteName(note.title);
    setShowRenameModal(true);
  };

  const confirmRename = async () => {
    if (renameNote && newNoteName.trim()) {
      try {
        await api.put(`/chat/rename/${renameNote.id}`, null, {
          params: { title: newNoteName.trim() }
        });
        setSavedNotes((prev) =>
          prev.map((n) => (n.id === renameNote.id ? { ...n, title: newNoteName.trim() } : n))
        );
        if (selectedNote?.id === renameNote.id) {
          setSelectedNote({ ...selectedNote, title: newNoteName.trim() });
        }
        setShowRenameModal(false);
        setRenameNote(null);
        setNewNoteName('');
      } catch (error) {
        Alert.alert('Error', 'Failed to rename note');
      }
    }
  };

  const toggleSave = (message: Message) => {
    if (message.saved) {
      unsaveMessage(message.id);
    } else {
      // Show title input modal
      setPendingSaveMessage(message);
      setNoteTitle('');
      setShowTitleModal(true);
    }
  };

  const confirmSave = () => {
    if (pendingSaveMessage && noteTitle.trim()) {
      saveMessage(pendingSaveMessage.id, noteTitle.trim());
      setShowTitleModal(false);
      setPendingSaveMessage(null);
      setNoteTitle('');
    }
  };

  const generateDefaultTitle = (content: string) => {
    // Generate a title from the first few words of the response
    const words = content.split(' ').slice(0, 6).join(' ');
    return words.length > 30 ? words.substring(0, 30) + '...' : words;
  };

  const clearHistory = async () => {
    Alert.alert(
      'Clear Chat',
      'This will delete all messages except saved ones. Continue?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Clear',
          style: 'destructive',
          onPress: async () => {
            try {
              await api.delete(`/chat/history/${profile?.id}`);
              setMessages((prev) => prev.filter((m) => m.saved));
            } catch (error) {
              Alert.alert('Error', 'Failed to clear history');
            }
          },
        },
      ]
    );
  };

  const suggestions = [
    'What should I eat before a workout?',
    'How can I build muscle faster?',
    'Tips for better sleep and recovery',
    'Best exercises for core strength',
  ];

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Title Input Modal */}
      <Modal
        visible={showTitleModal}
        transparent
        animationType="fade"
        onRequestClose={() => setShowTitleModal(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.titleModal}>
            <Text style={styles.titleModalHeader}>Save Note</Text>
            <Text style={styles.titleModalSubtext}>Give this response a title for easy access</Text>
            <TextInput
              style={styles.titleInput}
              placeholder="Enter a title..."
              placeholderTextColor={colors.textMuted}
              value={noteTitle}
              onChangeText={setNoteTitle}
              autoFocus
            />
            <View style={styles.titleModalActions}>
              <TouchableOpacity 
                style={styles.titleModalCancel}
                onPress={() => {
                  setShowTitleModal(false);
                  setPendingSaveMessage(null);
                }}
              >
                <Text style={styles.titleModalCancelText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity 
                style={[styles.titleModalSave, !noteTitle.trim() && styles.titleModalSaveDisabled]}
                onPress={confirmSave}
                disabled={!noteTitle.trim()}
              >
                <Ionicons name="bookmark" size={18} color={colors.background} />
                <Text style={styles.titleModalSaveText}>Save</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <Image
            source={require('../../assets/logo-icon-yellow.png')}
            style={styles.headerLogo}
            resizeMode="contain"
          />
          <View>
            <Text style={styles.title}>Ask InterFitAI</Text>
            <Text style={styles.subtitle}>Your AI fitness coach</Text>
          </View>
        </View>
        <TouchableOpacity onPress={clearHistory} style={styles.clearBtn}>
          <Ionicons name="trash-outline" size={20} color={colors.textSecondary} />
        </TouchableOpacity>
      </View>

      {/* Tabs */}
      <View style={styles.tabContainer}>
        <TouchableOpacity
          style={[styles.tab, activeTab === 'chat' && styles.tabActive]}
          onPress={() => setActiveTab('chat')}
        >
          <Ionicons 
            name="chatbubbles" 
            size={18} 
            color={activeTab === 'chat' ? colors.primary : colors.textSecondary} 
          />
          <Text style={[styles.tabText, activeTab === 'chat' && styles.tabTextActive]}>Chat</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.tab, activeTab === 'saved' && styles.tabActive]}
          onPress={() => setActiveTab('saved')}
        >
          <Ionicons 
            name="bookmark" 
            size={18} 
            color={activeTab === 'saved' ? colors.primary : colors.textSecondary} 
          />
          <Text style={[styles.tabText, activeTab === 'saved' && styles.tabTextActive]}>
            Saved ({savedNotes.length})
          </Text>
        </TouchableOpacity>
      </View>

      {/* Rename Modal */}
      <Modal
        visible={showRenameModal}
        transparent
        animationType="fade"
        onRequestClose={() => setShowRenameModal(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.titleModal}>
            <Text style={styles.titleModalHeader}>Rename Note</Text>
            <TextInput
              style={styles.titleInput}
              placeholder="Enter new title..."
              placeholderTextColor={colors.textMuted}
              value={newNoteName}
              onChangeText={setNewNoteName}
              autoFocus
            />
            <View style={styles.titleModalActions}>
              <TouchableOpacity 
                style={styles.titleModalCancel}
                onPress={() => {
                  setShowRenameModal(false);
                  setRenameNote(null);
                }}
              >
                <Text style={styles.titleModalCancelText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity 
                style={[styles.titleModalSave, !newNoteName.trim() && styles.titleModalSaveDisabled]}
                onPress={confirmRename}
                disabled={!newNoteName.trim()}
              >
                <Ionicons name="checkmark" size={18} color={colors.background} />
                <Text style={styles.titleModalSaveText}>Rename</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {activeTab === 'saved' ? (
        <ScrollView style={styles.savedContainer} contentContainerStyle={styles.savedContentContainer}>
          {selectedNote ? (
            // Full note view
            <View style={styles.noteDetailView}>
              <TouchableOpacity 
                style={styles.noteBackBtn}
                onPress={() => setSelectedNote(null)}
              >
                <Ionicons name="arrow-back" size={20} color={colors.primary} />
                <Text style={styles.noteBackText}>Back to Notes</Text>
              </TouchableOpacity>
              
              <View style={styles.noteDetailCard}>
                <View style={styles.noteDetailHeader}>
                  <Text style={styles.noteDetailTitle}>{selectedNote.title}</Text>
                  <TouchableOpacity onPress={() => openRenameModal(selectedNote)}>
                    <Ionicons name="pencil" size={20} color={colors.primary} />
                  </TouchableOpacity>
                </View>
                <Text style={styles.noteDetailDate}>
                  Saved on {new Date(selectedNote.created_at).toLocaleDateString('en-US', {
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric'
                  })}
                </Text>
                <View style={styles.noteDetailDivider} />
                <Text style={styles.noteDetailContent}>{selectedNote.content}</Text>
              </View>
            </View>
          ) : savedNotes.length === 0 ? (
            <View style={styles.emptyState}>
              <Ionicons name="folder-open-outline" size={48} color={colors.textMuted} />
              <Text style={styles.emptyTitle}>No Saved Notes</Text>
              <Text style={styles.emptySubtitle}>Tap the bookmark icon on any AI response to save it here</Text>
            </View>
          ) : (
            // Note list view
            <View style={styles.notesList}>
              <Text style={styles.notesListHeader}>{savedNotes.length} Saved Note{savedNotes.length !== 1 ? 's' : ''}</Text>
              <Text style={styles.notesListHint}>Long press to rename</Text>
              {savedNotes.map((note) => (
                <TouchableOpacity 
                  key={note.id} 
                  style={styles.noteCard}
                  onPress={() => setSelectedNote(note)}
                  onLongPress={() => openRenameModal(note)}
                  delayLongPress={500}
                >
                  <View style={styles.noteCardIcon}>
                    <Ionicons name="document-text" size={22} color={colors.primary} />
                  </View>
                  <View style={styles.noteCardContent}>
                    <Text style={styles.noteCardTitle} numberOfLines={1}>
                      {note.title}
                    </Text>
                    <Text style={styles.noteCardPreview} numberOfLines={2}>
                      {note.content}
                    </Text>
                    <Text style={styles.noteCardDate}>
                      {new Date(note.created_at).toLocaleDateString()}
                    </Text>
                  </View>
                  <TouchableOpacity 
                    onPress={() => deleteNote(note.id)}
                    style={styles.noteCardDelete}
                  >
                    <Ionicons name="trash-outline" size={18} color={colors.error} />
                  </TouchableOpacity>
                </TouchableOpacity>
              ))}
            </View>
          )}
        </ScrollView>
      ) : (
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={styles.chatContainer}
          keyboardVerticalOffset={100}
        >
          <ScrollView
            ref={scrollViewRef}
            style={styles.messagesContainer}
            contentContainerStyle={styles.messagesContent}
          onContentSizeChange={() => scrollViewRef.current?.scrollToEnd({ animated: true })}
        >
          {historyLoading ? (
            <ActivityIndicator size="large" color={colors.primary} style={styles.loader} />
          ) : messages.length === 0 ? (
            <View style={styles.emptyState}>
              <Ionicons name="chatbubble-ellipses" size={64} color={colors.primary} />
              <Text style={styles.emptyTitle}>Ask Anything!</Text>
              <Text style={styles.emptyText}>
                Get expert advice on fitness, nutrition, workouts, and more.
              </Text>

              <Text style={styles.suggestionsTitle}>Try asking:</Text>
              <View style={styles.suggestions}>
                {suggestions.map((suggestion, idx) => (
                  <TouchableOpacity
                    key={idx}
                    style={styles.suggestionBtn}
                    onPress={() => setInput(suggestion)}
                  >
                    <Text style={styles.suggestionText}>{suggestion}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>
          ) : (
            messages.map((message) => (
              <View
                key={message.id}
                style={[
                  styles.messageBubble,
                  message.role === 'user' ? styles.userMessage : styles.aiMessage,
                ]}
              >
                {message.role === 'assistant' && (
                  <View style={styles.aiHeader}>
                    <View style={styles.aiAvatar}>
                      <Ionicons name="sparkles" size={14} color={colors.primary} />
                    </View>
                    <Text style={styles.aiLabel}>InterFitAI</Text>
                    <TouchableOpacity
                      onPress={() => toggleSave(message)}
                      style={styles.saveBtn}
                    >
                      <Ionicons
                        name={message.saved ? 'bookmark' : 'bookmark-outline'}
                        size={18}
                        color={message.saved ? colors.primary : colors.textSecondary}
                      />
                    </TouchableOpacity>
                  </View>
                )}
                <Text
                  style={[
                    styles.messageText,
                    message.role === 'user' && styles.userMessageText,
                  ]}
                >
                  {message.content}
                </Text>
              </View>
            ))
          )}

          {loading && (
            <View style={[styles.messageBubble, styles.aiMessage]}>
              <View style={styles.typingIndicator}>
                <View style={styles.typingDot} />
                <View style={[styles.typingDot, styles.typingDot2]} />
                <View style={[styles.typingDot, styles.typingDot3]} />
              </View>
            </View>
          )}
        </ScrollView>

        <View style={styles.inputContainer}>
          <TextInput
            style={styles.input}
            placeholder="Ask anything about fitness..."
            placeholderTextColor={colors.textMuted}
            value={input}
            onChangeText={setInput}
            multiline
            maxLength={1000}
          />
          <TouchableOpacity
            style={[styles.sendBtn, !input.trim() && styles.sendBtnDisabled]}
            onPress={sendMessage}
            disabled={!input.trim() || loading}
          >
            <Ionicons
              name="send"
              size={20}
              color={input.trim() ? colors.background : colors.textMuted}
            />
          </TouchableOpacity>
        </View>
        </KeyboardAvoidingView>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 20,
    paddingBottom: 12,
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  headerLogo: {
    width: 40,
    height: 40,
  },
  title: {
    fontSize: 22,
    fontWeight: '700',
    color: colors.text,
  },
  subtitle: {
    fontSize: 14,
    color: colors.textSecondary,
    marginTop: 2,
  },
  clearBtn: {
    padding: 8,
  },
  chatContainer: {
    flex: 1,
  },
  messagesContainer: {
    flex: 1,
  },
  messagesContent: {
    padding: 20,
    paddingBottom: 20,
  },
  loader: {
    marginTop: 40,
  },
  emptyState: {
    alignItems: 'center',
    paddingVertical: 40,
  },
  emptyTitle: {
    fontSize: 24,
    fontWeight: '700',
    color: colors.text,
    marginTop: 16,
  },
  emptyText: {
    fontSize: 14,
    color: colors.textSecondary,
    textAlign: 'center',
    marginTop: 8,
    paddingHorizontal: 20,
  },
  suggestionsTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.textSecondary,
    marginTop: 32,
    marginBottom: 12,
  },
  suggestions: {
    gap: 8,
    width: '100%',
  },
  suggestionBtn: {
    backgroundColor: colors.surface,
    padding: 14,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.border,
  },
  suggestionText: {
    fontSize: 14,
    color: colors.text,
    textAlign: 'center',
  },
  messageBubble: {
    maxWidth: '85%',
    padding: 14,
    borderRadius: 16,
    marginBottom: 12,
  },
  userMessage: {
    alignSelf: 'flex-end',
    backgroundColor: colors.primary,
    borderBottomRightRadius: 4,
  },
  aiMessage: {
    alignSelf: 'flex-start',
    backgroundColor: colors.surface,
    borderBottomLeftRadius: 4,
  },
  aiHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
  },
  aiAvatar: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: colors.primary + '20',
    justifyContent: 'center',
    alignItems: 'center',
  },
  aiLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.primary,
    marginLeft: 6,
    flex: 1,
  },
  saveBtn: {
    padding: 4,
  },
  messageText: {
    fontSize: 15,
    color: colors.text,
    lineHeight: 22,
  },
  userMessageText: {
    color: colors.background,
  },
  typingIndicator: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingVertical: 8,
    paddingHorizontal: 4,
  },
  typingDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.primary,
    opacity: 0.4,
  },
  typingDot2: {
    opacity: 0.6,
  },
  typingDot3: {
    opacity: 0.8,
  },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    padding: 16,
    paddingBottom: Platform.OS === 'ios' ? 24 : 16,
    backgroundColor: colors.surface,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    gap: 12,
  },
  input: {
    flex: 1,
    backgroundColor: colors.surfaceLight,
    borderRadius: 24,
    paddingHorizontal: 16,
    paddingVertical: 12,
    paddingRight: 16,
    fontSize: 15,
    color: colors.text,
    maxHeight: 100,
  },
  sendBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
  },
  sendBtnDisabled: {
    backgroundColor: colors.surfaceLight,
  },
  tabContainer: {
    flexDirection: 'row',
    paddingHorizontal: 20,
    marginBottom: 8,
    gap: 12,
  },
  tab: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 20,
    backgroundColor: colors.surface,
    gap: 6,
  },
  tabActive: {
    backgroundColor: colors.primary + '20',
  },
  tabText: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  tabTextActive: {
    color: colors.primary,
  },
  savedContainer: {
    flex: 1,
  },
  savedContentContainer: {
    padding: 20,
    paddingBottom: 40,
  },
  savedCard: {
    backgroundColor: colors.surface,
    padding: 16,
    borderRadius: 12,
    borderLeftWidth: 3,
    borderLeftColor: colors.primary,
  },
  savedCardContent: {
    fontSize: 14,
    color: colors.text,
    lineHeight: 20,
  },
  savedFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: colors.surfaceLight,
  },
  savedDate: {
    fontSize: 12,
    color: colors.textSecondary,
  },
  // Note List Styles
  notesList: {
    gap: 12,
  },
  notesListHeader: {
    fontSize: 14,
    fontWeight: '500',
    color: colors.textSecondary,
    marginBottom: 4,
  },
  notesListHint: {
    fontSize: 12,
    color: colors.textMuted,
    marginBottom: 12,
  },
  noteCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    padding: 14,
    borderRadius: 12,
    gap: 12,
  },
  noteCardIcon: {
    width: 44,
    height: 44,
    borderRadius: 10,
    backgroundColor: colors.primary + '15',
    justifyContent: 'center',
    alignItems: 'center',
  },
  noteCardContent: {
    flex: 1,
  },
  noteCardTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.text,
  },
  noteCardPreview: {
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: 2,
    lineHeight: 18,
  },
  noteCardDate: {
    fontSize: 11,
    color: colors.textMuted,
    marginTop: 4,
  },
  noteCardDelete: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.error + '15',
    justifyContent: 'center',
    alignItems: 'center',
  },
  // Note Detail View Styles
  noteDetailView: {
    flex: 1,
  },
  noteBackBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 16,
  },
  noteBackText: {
    fontSize: 15,
    fontWeight: '500',
    color: colors.primary,
  },
  noteDetailCard: {
    backgroundColor: colors.surface,
    borderRadius: 16,
    padding: 20,
  },
  noteDetailHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  noteDetailTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: colors.text,
    flex: 1,
    marginRight: 12,
  },
  noteDetailDate: {
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: 4,
  },
  noteDetailDivider: {
    height: 1,
    backgroundColor: colors.border,
    marginVertical: 16,
  },
  noteDetailContent: {
    fontSize: 15,
    color: colors.text,
    lineHeight: 24,
  },
  // Title Modal Styles
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.6)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  titleModal: {
    backgroundColor: colors.surface,
    borderRadius: 20,
    padding: 24,
    width: '100%',
    maxWidth: 340,
  },
  titleModalHeader: {
    fontSize: 20,
    fontWeight: '700',
    color: colors.text,
    textAlign: 'center',
  },
  titleModalSubtext: {
    fontSize: 14,
    color: colors.textSecondary,
    textAlign: 'center',
    marginTop: 6,
    marginBottom: 20,
  },
  titleInput: {
    backgroundColor: colors.surfaceLight,
    borderRadius: 12,
    padding: 14,
    fontSize: 16,
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.border,
  },
  titleModalActions: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 20,
  },
  titleModalCancel: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 12,
    backgroundColor: colors.surfaceLight,
    alignItems: 'center',
  },
  titleModalCancelText: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  titleModalSave: {
    flex: 1,
    flexDirection: 'row',
    paddingVertical: 14,
    borderRadius: 12,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
  },
  titleModalSaveDisabled: {
    opacity: 0.5,
  },
  titleModalSaveText: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.background,
  },
});