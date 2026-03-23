import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useUserStore } from '../src/store/userStore';
import { colors } from '../src/theme/colors';
import api from '../src/services/api';

interface FreeAccessUser {
  email: string;
  granted_by: string;
  reason: string;
  granted_at: string;
}

export default function AdminScreen() {
  const router = useRouter();
  const { profile } = useUserStore();
  const [email, setEmail] = useState('');
  const [reason, setReason] = useState('');
  const [loading, setLoading] = useState(false);
  const [freeAccessList, setFreeAccessList] = useState<FreeAccessUser[]>([]);
  const [listLoading, setListLoading] = useState(true);
  
  // Admin emails
  const ADMIN_EMAILS = ['sebastianrush5@gmail.com', 'srush@interfitai.com'];
  const isAdmin = profile?.email && ADMIN_EMAILS.includes(profile.email.toLowerCase());

  useEffect(() => {
    if (isAdmin) {
      loadFreeAccessList();
    }
  }, [isAdmin]);

  const loadFreeAccessList = async () => {
    try {
      setListLoading(true);
      const response = await api.get(`/admin/free-access-list?admin_email=${encodeURIComponent(profile?.email || '')}`);
      setFreeAccessList(response.data || []);
    } catch (error) {
      console.log('Failed to load free access list:', error);
    } finally {
      setListLoading(false);
    }
  };

  const handleGrantAccess = async () => {
    if (!email.trim()) {
      Alert.alert('Error', 'Please enter a user email');
      return;
    }

    // Basic email validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email.trim())) {
      Alert.alert('Error', 'Please enter a valid email address');
      return;
    }

    setLoading(true);
    try {
      await api.post('/admin/grant-access', {
        admin_email: profile?.email,
        user_email: email.trim().toLowerCase(),
        reason: reason.trim() || 'Admin granted',
      });
      
      Alert.alert('Success', `Free access granted to ${email}`);
      setEmail('');
      setReason('');
      loadFreeAccessList();
    } catch (error: any) {
      Alert.alert('Error', error.response?.data?.detail || 'Failed to grant access');
    } finally {
      setLoading(false);
    }
  };

  const handleRevokeAccess = async (userEmail: string) => {
    Alert.alert(
      'Revoke Access',
      `Are you sure you want to revoke free access from ${userEmail}?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Revoke',
          style: 'destructive',
          onPress: async () => {
            try {
              await api.delete(`/admin/revoke-access?admin_email=${encodeURIComponent(profile?.email || '')}&user_email=${encodeURIComponent(userEmail)}`);
              Alert.alert('Success', `Access revoked from ${userEmail}`);
              loadFreeAccessList();
            } catch (error: any) {
              Alert.alert('Error', error.response?.data?.detail || 'Failed to revoke access');
            }
          },
        },
      ]
    );
  };

  if (!isAdmin) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
            <Ionicons name="arrow-back" size={24} color={colors.text} />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Admin Panel</Text>
          <View style={{ width: 40 }} />
        </View>
        <View style={styles.notAuthorized}>
          <Ionicons name="lock-closed" size={60} color={colors.textMuted} />
          <Text style={styles.notAuthorizedText}>You are not authorized to access this page</Text>
          <TouchableOpacity style={styles.goBackBtn} onPress={() => router.back()}>
            <Text style={styles.goBackBtnText}>Go Back</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView 
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={{ flex: 1 }}
      >
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
            <Ionicons name="arrow-back" size={24} color={colors.text} />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Admin Panel</Text>
          <View style={{ width: 40 }} />
        </View>

        <ScrollView style={styles.content} showsVerticalScrollIndicator={false}>
          {/* Grant Access Section */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Grant Free Access</Text>
            <Text style={styles.sectionDescription}>
              Give a user free premium access to InterFitAI
            </Text>

            <View style={styles.inputGroup}>
              <Text style={styles.label}>User Email</Text>
              <View style={styles.inputContainer}>
                <Ionicons name="mail-outline" size={20} color={colors.textMuted} style={styles.inputIcon} />
                <TextInput
                  style={styles.input}
                  placeholder="Enter user's email"
                  placeholderTextColor={colors.textMuted}
                  value={email}
                  onChangeText={setEmail}
                  keyboardType="email-address"
                  autoCapitalize="none"
                  autoCorrect={false}
                />
              </View>
            </View>

            <View style={styles.inputGroup}>
              <Text style={styles.label}>Reason (optional)</Text>
              <View style={styles.inputContainer}>
                <Ionicons name="document-text-outline" size={20} color={colors.textMuted} style={styles.inputIcon} />
                <TextInput
                  style={styles.input}
                  placeholder="e.g., Beta tester, Influencer"
                  placeholderTextColor={colors.textMuted}
                  value={reason}
                  onChangeText={setReason}
                />
              </View>
            </View>

            <TouchableOpacity
              style={[styles.grantBtn, loading && styles.grantBtnDisabled]}
              onPress={handleGrantAccess}
              disabled={loading}
            >
              {loading ? (
                <ActivityIndicator color="#000" />
              ) : (
                <>
                  <Ionicons name="gift" size={20} color="#000" />
                  <Text style={styles.grantBtnText}>Grant Access</Text>
                </>
              )}
            </TouchableOpacity>
          </View>

          {/* Free Access List */}
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Users with Free Access</Text>
            
            {listLoading ? (
              <ActivityIndicator color={colors.primary} style={{ marginTop: 20 }} />
            ) : freeAccessList.length === 0 ? (
              <Text style={styles.emptyText}>No users with free access</Text>
            ) : (
              freeAccessList.map((user, index) => (
                <View key={index} style={styles.userCard}>
                  <View style={styles.userInfo}>
                    <Text style={styles.userEmail}>{user.email}</Text>
                    <Text style={styles.userReason}>{user.reason || 'No reason'}</Text>
                    <Text style={styles.userDate}>
                      Granted: {new Date(user.granted_at).toLocaleDateString()}
                    </Text>
                  </View>
                  <TouchableOpacity
                    style={styles.revokeBtn}
                    onPress={() => handleRevokeAccess(user.email)}
                  >
                    <Ionicons name="trash-outline" size={20} color={colors.error} />
                  </TouchableOpacity>
                </View>
              ))
            )}
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
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
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  backBtn: {
    padding: 8,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  content: {
    flex: 1,
    padding: 16,
  },
  section: {
    marginBottom: 32,
  },
  sectionTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: colors.text,
    marginBottom: 8,
  },
  sectionDescription: {
    fontSize: 14,
    color: colors.textSecondary,
    marginBottom: 20,
  },
  inputGroup: {
    marginBottom: 16,
  },
  label: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 8,
  },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.border,
  },
  inputIcon: {
    paddingLeft: 16,
  },
  input: {
    flex: 1,
    padding: 16,
    fontSize: 16,
    color: colors.text,
  },
  grantBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: colors.primary,
    paddingVertical: 16,
    borderRadius: 12,
    marginTop: 8,
  },
  grantBtnDisabled: {
    opacity: 0.6,
  },
  grantBtnText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#000',
  },
  emptyText: {
    fontSize: 14,
    color: colors.textMuted,
    textAlign: 'center',
    marginTop: 20,
  },
  userCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    padding: 16,
    borderRadius: 12,
    marginTop: 12,
  },
  userInfo: {
    flex: 1,
  },
  userEmail: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
  userReason: {
    fontSize: 14,
    color: colors.textSecondary,
    marginTop: 4,
  },
  userDate: {
    fontSize: 12,
    color: colors.textMuted,
    marginTop: 4,
  },
  revokeBtn: {
    padding: 12,
  },
  notAuthorized: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  notAuthorizedText: {
    fontSize: 16,
    color: colors.textSecondary,
    textAlign: 'center',
    marginTop: 16,
  },
  goBackBtn: {
    backgroundColor: colors.primary,
    paddingVertical: 12,
    paddingHorizontal: 24,
    borderRadius: 12,
    marginTop: 24,
  },
  goBackBtnText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#000',
  },
});
