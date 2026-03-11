import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Switch,
  Alert,
  Platform,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { colors } from '../src/styles/colors';
import {
  WorkoutReminder,
  loadReminders,
  saveReminders,
  registerForPushNotificationsAsync,
} from '../src/services/notifications';
import {
  isHealthAvailable,
  requestHealthPermissions,
  syncHealthData,
  getHealthConnectionStatus,
  HealthData,
} from '../src/services/health';

const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

export default function SettingsScreen() {
  const router = useRouter();
  const [reminders, setReminders] = useState<WorkoutReminder[]>([]);
  const [healthConnected, setHealthConnected] = useState(false);
  const [healthAvailable, setHealthAvailable] = useState(false);
  const [healthData, setHealthData] = useState<HealthData | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncingHealth, setSyncingHealth] = useState(false);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      // Load reminders
      const savedReminders = await loadReminders();
      setReminders(savedReminders);

      // Check health availability
      const healthStatus = await getHealthConnectionStatus();
      setHealthAvailable(healthStatus.available);
      setHealthConnected(healthStatus.connected);

      if (healthStatus.connected) {
        const data = await syncHealthData();
        setHealthData(data);
      }
    } catch (error) {
      console.error('Error loading settings:', error);
    } finally {
      setLoading(false);
    }
  };

  const toggleReminder = async (index: number) => {
    const updated = [...reminders];
    updated[index].enabled = !updated[index].enabled;
    setReminders(updated);
    
    // Request notification permissions if enabling
    if (updated[index].enabled) {
      await registerForPushNotificationsAsync();
    }
    
    await saveReminders(updated);
  };

  const connectHealth = async () => {
    if (!healthAvailable) {
      Alert.alert(
        'Not Available',
        Platform.OS === 'ios' 
          ? 'Apple Health is not available on this device. Please use a physical iPhone with iOS 8.0 or later.'
          : 'Health Connect is not available on this device.',
        [{ text: 'OK' }]
      );
      return;
    }

    const granted = await requestHealthPermissions();
    if (granted) {
      setHealthConnected(true);
      setSyncingHealth(true);
      const data = await syncHealthData();
      setHealthData(data);
      setSyncingHealth(false);
      Alert.alert('Connected', 'Successfully connected to Apple Health!');
    } else {
      Alert.alert(
        'Permission Denied',
        'Please enable Health permissions in your device settings to sync your fitness data.',
        [{ text: 'OK' }]
      );
    }
  };

  const handleSyncHealth = async () => {
    setSyncingHealth(true);
    try {
      const data = await syncHealthData();
      setHealthData(data);
      Alert.alert('Synced', 'Health data updated successfully!');
    } catch (error) {
      Alert.alert('Error', 'Failed to sync health data');
    } finally {
      setSyncingHealth(false);
    }
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <ActivityIndicator size="large" color={colors.primary} style={styles.loader} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Settings</Text>
        <View style={styles.backBtn} />
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        {/* Health Connection */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Ionicons name="heart" size={22} color={colors.primary} />
            <Text style={styles.sectionTitle}>Health Integration</Text>
          </View>
          
          <View style={styles.card}>
            <View style={styles.healthRow}>
              <View style={styles.healthInfo}>
                <Ionicons 
                  name={Platform.OS === 'ios' ? 'logo-apple' : 'fitness'} 
                  size={28} 
                  color={healthConnected ? colors.success : colors.textMuted} 
                />
                <View style={styles.healthTextContainer}>
                  <Text style={styles.healthTitle}>
                    {Platform.OS === 'ios' ? 'Apple Health' : 'Health Connect'}
                  </Text>
                  <Text style={styles.healthSubtitle}>
                    {healthConnected ? 'Connected' : 'Not connected'}
                  </Text>
                </View>
              </View>
              
              {healthConnected ? (
                <TouchableOpacity 
                  style={styles.syncBtn}
                  onPress={handleSyncHealth}
                  disabled={syncingHealth}
                >
                  {syncingHealth ? (
                    <ActivityIndicator size="small" color={colors.primary} />
                  ) : (
                    <>
                      <Ionicons name="sync" size={16} color={colors.primary} />
                      <Text style={styles.syncBtnText}>Sync</Text>
                    </>
                  )}
                </TouchableOpacity>
              ) : (
                <TouchableOpacity 
                  style={styles.connectBtn}
                  onPress={connectHealth}
                >
                  <Text style={styles.connectBtnText}>Connect</Text>
                </TouchableOpacity>
              )}
            </View>

            {healthConnected && healthData && (
              <View style={styles.healthStats}>
                <View style={styles.healthStat}>
                  <Ionicons name="footsteps" size={20} color={colors.textSecondary} />
                  <Text style={styles.healthStatValue}>{healthData.steps.toLocaleString()}</Text>
                  <Text style={styles.healthStatLabel}>Steps</Text>
                </View>
                <View style={styles.healthStat}>
                  <Ionicons name="flame" size={20} color={colors.textSecondary} />
                  <Text style={styles.healthStatValue}>{healthData.calories}</Text>
                  <Text style={styles.healthStatLabel}>Cal Burned</Text>
                </View>
                <View style={styles.healthStat}>
                  <Ionicons name="walk" size={20} color={colors.textSecondary} />
                  <Text style={styles.healthStatValue}>{healthData.distance} km</Text>
                  <Text style={styles.healthStatLabel}>Distance</Text>
                </View>
              </View>
            )}

            <Text style={styles.healthDesc}>
              {healthConnected 
                ? 'Your workouts will automatically sync to your health app'
                : 'Connect to sync steps, calories, and workouts'}
            </Text>
          </View>
        </View>

        {/* Workout Reminders */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Ionicons name="notifications" size={22} color={colors.primary} />
            <Text style={styles.sectionTitle}>Workout Reminders</Text>
          </View>
          
          <View style={styles.card}>
            <Text style={styles.reminderDesc}>
              Get reminded to train on your preferred days
            </Text>
            
            <View style={styles.reminderGrid}>
              {reminders.map((reminder, index) => (
                <View key={reminder.id} style={styles.reminderItem}>
                  <Text style={[
                    styles.reminderDay,
                    reminder.enabled && styles.reminderDayActive
                  ]}>
                    {DAYS[reminder.dayOfWeek]}
                  </Text>
                  <Text style={styles.reminderTime}>
                    {reminder.hour}:{reminder.minute.toString().padStart(2, '0')} AM
                  </Text>
                  <Switch
                    value={reminder.enabled}
                    onValueChange={() => toggleReminder(index)}
                    trackColor={{ false: colors.border, true: colors.primary + '60' }}
                    thumbColor={reminder.enabled ? colors.primary : colors.textMuted}
                    ios_backgroundColor={colors.border}
                  />
                </View>
              ))}
            </View>
          </View>
        </View>

        {/* App Info */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Ionicons name="information-circle" size={22} color={colors.primary} />
            <Text style={styles.sectionTitle}>About</Text>
          </View>
          
          <View style={styles.card}>
            <View style={styles.aboutRow}>
              <Text style={styles.aboutLabel}>Version</Text>
              <Text style={styles.aboutValue}>1.0.0</Text>
            </View>
            <View style={styles.aboutRow}>
              <Text style={styles.aboutLabel}>Build</Text>
              <Text style={styles.aboutValue}>2025.03</Text>
            </View>
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  loader: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
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
    width: 40,
    height: 40,
    justifyContent: 'center',
    alignItems: 'center',
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  scrollContent: {
    padding: 16,
    paddingBottom: 40,
  },
  section: {
    marginBottom: 24,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
  },
  card: {
    backgroundColor: colors.surface,
    borderRadius: 16,
    padding: 16,
  },
  healthRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  healthInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  healthTextContainer: {
    gap: 2,
  },
  healthTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
  healthSubtitle: {
    fontSize: 13,
    color: colors.textSecondary,
  },
  connectBtn: {
    backgroundColor: colors.primary,
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 20,
  },
  connectBtnText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#000',
  },
  syncBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: colors.primary + '20',
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 20,
  },
  syncBtnText: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.primary,
  },
  healthStats: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    marginTop: 16,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  healthStat: {
    alignItems: 'center',
    gap: 4,
  },
  healthStatValue: {
    fontSize: 18,
    fontWeight: '700',
    color: colors.text,
  },
  healthStatLabel: {
    fontSize: 12,
    color: colors.textSecondary,
  },
  healthDesc: {
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: 12,
    textAlign: 'center',
  },
  reminderDesc: {
    fontSize: 14,
    color: colors.textSecondary,
    marginBottom: 16,
  },
  reminderGrid: {
    gap: 8,
  },
  reminderItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  reminderDay: {
    fontSize: 16,
    fontWeight: '500',
    color: colors.textSecondary,
    width: 50,
  },
  reminderDayActive: {
    color: colors.primary,
    fontWeight: '700',
  },
  reminderTime: {
    fontSize: 14,
    color: colors.textSecondary,
    flex: 1,
    textAlign: 'center',
  },
  aboutRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  aboutLabel: {
    fontSize: 15,
    color: colors.textSecondary,
  },
  aboutValue: {
    fontSize: 15,
    fontWeight: '500',
    color: colors.text,
  },
});
