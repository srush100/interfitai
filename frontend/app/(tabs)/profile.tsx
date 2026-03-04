import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Switch,
  Alert,
  TextInput,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Pedometer } from 'expo-sensors';
import { useUserStore } from '../../src/store/userStore';
import { colors } from '../../src/theme/colors';
import api from '../../src/services/api';

const DEVICES = [
  { id: 'apple_health', name: 'Apple Health', icon: 'fitness' },
  { id: 'google_fit', name: 'Google Fit', icon: 'logo-google' },
  { id: 'fitbit', name: 'Fitbit', icon: 'watch' },
  { id: 'garmin', name: 'Garmin', icon: 'navigate' },
];

export default function ProfileScreen() {
  const router = useRouter();
  const { profile, updateProfile, setOnboarded } = useUserStore();
  const [editing, setEditing] = useState(false);
  const [editData, setEditData] = useState({
    weight: profile?.weight?.toString() || '',
    height: profile?.height?.toString() || '',
    age: profile?.age?.toString() || '',
  });
  const [saving, setSaving] = useState(false);
  const [isPedometerAvailable, setIsPedometerAvailable] = useState(false);
  const [stepCount, setStepCount] = useState(0);
  const [connectedDevices, setConnectedDevices] = useState<string[]>([]);
  const [stepGoal, setStepGoal] = useState(10000);

  useEffect(() => {
    checkPedometer();
    loadDevices();
    loadStepGoal();
  }, []);

  const checkPedometer = async () => {
    const available = await Pedometer.isAvailableAsync();
    setIsPedometerAvailable(available);

    if (available) {
      const end = new Date();
      const start = new Date();
      start.setHours(0, 0, 0, 0);

      const result = await Pedometer.getStepCountAsync(start, end);
      if (result) {
        setStepCount(result.steps);
        // Log steps to backend
        if (profile?.id) {
          try {
            await api.post(`/steps/log?user_id=${profile.id}&steps=${result.steps}&source=device`);
          } catch (error) {
            console.log('Error logging steps:', error);
          }
        }
      }
    }
  };

  const loadDevices = async () => {
    if (!profile?.id) return;
    try {
      const response = await api.get(`/devices/${profile.id}`);
      setConnectedDevices(response.data.filter((d: any) => d.connected).map((d: any) => d.device_type));
    } catch (error) {
      console.log('Error loading devices:', error);
    }
  };

  const loadStepGoal = async () => {
    if (!profile?.id) return;
    try {
      const response = await api.get(`/steps/goal/${profile.id}`);
      setStepGoal(response.data.daily_steps_goal);
    } catch (error) {
      console.log('Error loading step goal:', error);
    }
  };

  const handleSaveProfile = async () => {
    if (!editData.weight || !editData.height || !editData.age) {
      Alert.alert('Error', 'Please fill in all fields');
      return;
    }

    setSaving(true);
    try {
      await updateProfile({
        weight: parseFloat(editData.weight),
        height: parseFloat(editData.height),
        age: parseInt(editData.age),
      });
      setEditing(false);
    } catch (error) {
      Alert.alert('Error', 'Failed to update profile');
    } finally {
      setSaving(false);
    }
  };

  const toggleReminders = async (value: boolean) => {
    try {
      await updateProfile({ reminders_enabled: value });
    } catch (error) {
      Alert.alert('Error', 'Failed to update settings');
    }
  };

  const toggleMotivation = async (value: boolean) => {
    try {
      await updateProfile({ motivation_enabled: value });
    } catch (error) {
      Alert.alert('Error', 'Failed to update settings');
    }
  };

  const connectDevice = async (deviceId: string) => {
    if (!profile?.id) return;
    try {
      await api.post(`/devices/connect?user_id=${profile.id}&device_type=${deviceId}`);
      setConnectedDevices([...connectedDevices, deviceId]);
      Alert.alert('Success', `${deviceId.replace('_', ' ')} connected! (Demo mode)`);
    } catch (error) {
      Alert.alert('Error', 'Failed to connect device');
    }
  };

  const disconnectDevice = async (deviceId: string) => {
    if (!profile?.id) return;
    try {
      await api.delete(`/devices/disconnect?user_id=${profile.id}&device_type=${deviceId}`);
      setConnectedDevices(connectedDevices.filter((d) => d !== deviceId));
    } catch (error) {
      Alert.alert('Error', 'Failed to disconnect device');
    }
  };

  const updateStepGoal = async (newGoal: number) => {
    if (!profile?.id) return;
    try {
      await api.post('/steps/goal', {
        user_id: profile.id,
        daily_steps_goal: newGoal,
      });
      setStepGoal(newGoal);
    } catch (error) {
      Alert.alert('Error', 'Failed to update step goal');
    }
  };

  const handleLogout = () => {
    Alert.alert(
      'Reset Profile',
      'This will reset your profile. Continue?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Reset',
          style: 'destructive',
          onPress: async () => {
            await setOnboarded(false);
            router.replace('/onboarding');
          },
        },
      ]
    );
  };

  const macros = profile?.calculated_macros;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        <Text style={styles.title}>Profile</Text>

        {/* User Info Card */}
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <View style={styles.avatar}>
              <Ionicons name="person" size={32} color={colors.primary} />
            </View>
            <View style={styles.userInfo}>
              <Text style={styles.userName}>{profile?.name || 'User'}</Text>
              <Text style={styles.userGoal}>
                Goal: {profile?.goal?.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
              </Text>
            </View>
            <TouchableOpacity
              style={styles.editBtn}
              onPress={() => setEditing(!editing)}
            >
              <Ionicons name={editing ? 'close' : 'pencil'} size={20} color={colors.primary} />
            </TouchableOpacity>
          </View>

          {editing ? (
            <View style={styles.editForm}>
              <View style={styles.editRow}>
                <View style={styles.editField}>
                  <Text style={styles.editLabel}>Weight (kg)</Text>
                  <TextInput
                    style={styles.editInput}
                    value={editData.weight}
                    onChangeText={(text) => setEditData({ ...editData, weight: text })}
                    keyboardType="decimal-pad"
                  />
                </View>
                <View style={styles.editField}>
                  <Text style={styles.editLabel}>Height (cm)</Text>
                  <TextInput
                    style={styles.editInput}
                    value={editData.height}
                    onChangeText={(text) => setEditData({ ...editData, height: text })}
                    keyboardType="decimal-pad"
                  />
                </View>
                <View style={styles.editField}>
                  <Text style={styles.editLabel}>Age</Text>
                  <TextInput
                    style={styles.editInput}
                    value={editData.age}
                    onChangeText={(text) => setEditData({ ...editData, age: text })}
                    keyboardType="number-pad"
                  />
                </View>
              </View>
              <TouchableOpacity
                style={styles.saveBtn}
                onPress={handleSaveProfile}
                disabled={saving}
              >
                {saving ? (
                  <ActivityIndicator size="small" color={colors.background} />
                ) : (
                  <Text style={styles.saveBtnText}>Save Changes</Text>
                )}
              </TouchableOpacity>
            </View>
          ) : (
            <View style={styles.statsRow}>
              <View style={styles.stat}>
                <Text style={styles.statValue}>{profile?.weight}kg</Text>
                <Text style={styles.statLabel}>Weight</Text>
              </View>
              <View style={styles.stat}>
                <Text style={styles.statValue}>{profile?.height}cm</Text>
                <Text style={styles.statLabel}>Height</Text>
              </View>
              <View style={styles.stat}>
                <Text style={styles.statValue}>{profile?.age}</Text>
                <Text style={styles.statLabel}>Age</Text>
              </View>
            </View>
          )}
        </View>

        {/* Macros Card */}
        {macros && (
          <View style={styles.card}>
            <Text style={styles.sectionTitle}>Your Daily Macros</Text>
            <View style={styles.macrosGrid}>
              <View style={styles.macroItem}>
                <Text style={[styles.macroValue, { color: colors.primary }]}>{macros.calories}</Text>
                <Text style={styles.macroLabel}>Calories</Text>
              </View>
              <View style={styles.macroItem}>
                <Text style={[styles.macroValue, { color: '#FF6B6B' }]}>{macros.protein}g</Text>
                <Text style={styles.macroLabel}>Protein</Text>
              </View>
              <View style={styles.macroItem}>
                <Text style={[styles.macroValue, { color: '#4ECDC4' }]}>{macros.carbs}g</Text>
                <Text style={styles.macroLabel}>Carbs</Text>
              </View>
              <View style={styles.macroItem}>
                <Text style={[styles.macroValue, { color: '#FFD93D' }]}>{macros.fats}g</Text>
                <Text style={styles.macroLabel}>Fats</Text>
              </View>
            </View>
            <View style={styles.tdeeRow}>
              <Text style={styles.tdeeLabel}>TDEE: {macros.tdee} cal</Text>
              <Text style={styles.tdeeLabel}>BMR: {macros.bmr} cal</Text>
            </View>
          </View>
        )}

        {/* Step Tracking */}
        <View style={styles.card}>
          <Text style={styles.sectionTitle}>Step Tracking</Text>
          <View style={styles.stepsDisplay}>
            <Ionicons name="footsteps" size={32} color={colors.primary} />
            <View style={styles.stepsInfo}>
              <Text style={styles.stepsValue}>{stepCount.toLocaleString()}</Text>
              <Text style={styles.stepsGoal}>/ {stepGoal.toLocaleString()} steps</Text>
            </View>
          </View>
          <View style={styles.stepGoalBtns}>
            {[5000, 10000, 15000].map((goal) => (
              <TouchableOpacity
                key={goal}
                style={[styles.stepGoalBtn, stepGoal === goal && styles.stepGoalBtnActive]}
                onPress={() => updateStepGoal(goal)}
              >
                <Text style={[styles.stepGoalBtnText, stepGoal === goal && styles.stepGoalBtnTextActive]}>
                  {(goal / 1000)}K
                </Text>
              </TouchableOpacity>
            ))}
          </View>
          {!isPedometerAvailable && (
            <Text style={styles.pedometerWarning}>
              Step counting not available on this device
            </Text>
          )}
        </View>

        {/* Connected Devices */}
        <View style={styles.card}>
          <Text style={styles.sectionTitle}>Connected Devices</Text>
          {DEVICES.map((device) => (
            <View key={device.id} style={styles.deviceRow}>
              <View style={styles.deviceInfo}>
                <Ionicons name={device.icon as any} size={24} color={colors.textSecondary} />
                <Text style={styles.deviceName}>{device.name}</Text>
              </View>
              <TouchableOpacity
                style={[
                  styles.connectBtn,
                  connectedDevices.includes(device.id) && styles.disconnectBtn,
                ]}
                onPress={() =>
                  connectedDevices.includes(device.id)
                    ? disconnectDevice(device.id)
                    : connectDevice(device.id)
                }
              >
                <Text
                  style={[
                    styles.connectBtnText,
                    connectedDevices.includes(device.id) && styles.disconnectBtnText,
                  ]}
                >
                  {connectedDevices.includes(device.id) ? 'Disconnect' : 'Connect'}
                </Text>
              </TouchableOpacity>
            </View>
          ))}
        </View>

        {/* Settings */}
        <View style={styles.card}>
          <Text style={styles.sectionTitle}>Notifications</Text>
          
          <View style={styles.settingRow}>
            <View style={styles.settingInfo}>
              <Ionicons name="notifications" size={22} color={colors.textSecondary} />
              <Text style={styles.settingLabel}>Workout Reminders</Text>
            </View>
            <Switch
              value={profile?.reminders_enabled ?? true}
              onValueChange={toggleReminders}
              trackColor={{ false: colors.surfaceLight, true: colors.primary + '50' }}
              thumbColor={profile?.reminders_enabled ? colors.primary : colors.textMuted}
            />
          </View>

          <View style={styles.settingRow}>
            <View style={styles.settingInfo}>
              <Ionicons name="flash" size={22} color={colors.textSecondary} />
              <Text style={styles.settingLabel}>Daily Motivation</Text>
            </View>
            <Switch
              value={profile?.motivation_enabled ?? true}
              onValueChange={toggleMotivation}
              trackColor={{ false: colors.surfaceLight, true: colors.primary + '50' }}
              thumbColor={profile?.motivation_enabled ? colors.primary : colors.textMuted}
            />
          </View>
        </View>

        {/* Subscription */}
        <TouchableOpacity
          style={styles.subscriptionCard}
          onPress={() => router.push('/subscription')}
        >
          <View style={styles.subscriptionInfo}>
            <Ionicons name="diamond" size={24} color={colors.primary} />
            <View style={styles.subscriptionText}>
              <Text style={styles.subscriptionTitle}>Premium Membership</Text>
              <Text style={styles.subscriptionStatus}>
                {profile?.subscription_status === 'free'
                  ? 'Upgrade for full access'
                  : `${profile?.subscription_status} plan active`}
              </Text>
            </View>
          </View>
          <Ionicons name="chevron-forward" size={24} color={colors.textSecondary} />
        </TouchableOpacity>

        {/* Reset */}
        <TouchableOpacity style={styles.logoutBtn} onPress={handleLogout}>
          <Ionicons name="log-out" size={20} color={colors.error} />
          <Text style={styles.logoutText}>Reset Profile</Text>
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  scrollContent: {
    padding: 20,
    paddingBottom: 100,
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
    color: colors.text,
    marginBottom: 20,
  },
  card: {
    backgroundColor: colors.surface,
    borderRadius: 16,
    padding: 20,
    marginBottom: 16,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  avatar: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.primary + '20',
    justifyContent: 'center',
    alignItems: 'center',
  },
  userInfo: {
    flex: 1,
    marginLeft: 16,
  },
  userName: {
    fontSize: 20,
    fontWeight: '600',
    color: colors.text,
  },
  userGoal: {
    fontSize: 14,
    color: colors.primary,
    marginTop: 2,
  },
  editBtn: {
    padding: 8,
  },
  statsRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    marginTop: 20,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  stat: {
    alignItems: 'center',
  },
  statValue: {
    fontSize: 20,
    fontWeight: '700',
    color: colors.text,
  },
  statLabel: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 4,
  },
  editForm: {
    marginTop: 16,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  editRow: {
    flexDirection: 'row',
    gap: 12,
  },
  editField: {
    flex: 1,
  },
  editLabel: {
    fontSize: 12,
    color: colors.textSecondary,
    marginBottom: 6,
  },
  editInput: {
    backgroundColor: colors.surfaceLight,
    borderRadius: 8,
    padding: 12,
    fontSize: 16,
    color: colors.text,
    textAlign: 'center',
  },
  saveBtn: {
    backgroundColor: colors.primary,
    padding: 14,
    borderRadius: 12,
    alignItems: 'center',
    marginTop: 16,
  },
  saveBtnText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.background,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 16,
  },
  macrosGrid: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  macroItem: {
    alignItems: 'center',
  },
  macroValue: {
    fontSize: 20,
    fontWeight: '700',
  },
  macroLabel: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 4,
  },
  tdeeRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 16,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  tdeeLabel: {
    fontSize: 13,
    color: colors.textSecondary,
  },
  stepsDisplay: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
    marginBottom: 16,
  },
  stepsInfo: {
    flexDirection: 'row',
    alignItems: 'baseline',
  },
  stepsValue: {
    fontSize: 32,
    fontWeight: '700',
    color: colors.primary,
  },
  stepsGoal: {
    fontSize: 16,
    color: colors.textSecondary,
    marginLeft: 4,
  },
  stepGoalBtns: {
    flexDirection: 'row',
    gap: 12,
  },
  stepGoalBtn: {
    flex: 1,
    padding: 12,
    borderRadius: 8,
    backgroundColor: colors.surfaceLight,
    alignItems: 'center',
  },
  stepGoalBtnActive: {
    backgroundColor: colors.primary + '20',
    borderWidth: 1,
    borderColor: colors.primary,
  },
  stepGoalBtnText: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  stepGoalBtnTextActive: {
    color: colors.primary,
  },
  pedometerWarning: {
    fontSize: 12,
    color: colors.warning,
    marginTop: 12,
    textAlign: 'center',
  },
  deviceRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  deviceInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  deviceName: {
    fontSize: 15,
    color: colors.text,
  },
  connectBtn: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: colors.primary,
  },
  disconnectBtn: {
    backgroundColor: colors.surfaceLight,
  },
  connectBtnText: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.background,
  },
  disconnectBtnText: {
    color: colors.textSecondary,
  },
  settingRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 12,
  },
  settingInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  settingLabel: {
    fontSize: 15,
    color: colors.text,
  },
  subscriptionCard: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: 16,
    padding: 20,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: colors.primary + '50',
  },
  subscriptionInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  subscriptionText: {
    gap: 4,
  },
  subscriptionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
  subscriptionStatus: {
    fontSize: 13,
    color: colors.primary,
  },
  logoutBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    padding: 16,
    marginTop: 8,
  },
  logoutText: {
    fontSize: 16,
    color: colors.error,
  },
});