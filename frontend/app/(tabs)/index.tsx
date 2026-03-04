import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useUserStore } from '../../src/store/userStore';
import { colors } from '../../src/theme/colors';
import api from '../../src/services/api';

export default function HomeScreen() {
  const router = useRouter();
  const { profile } = useUserStore();
  const [refreshing, setRefreshing] = useState(false);
  const [motivation, setMotivation] = useState('');
  const [todaySteps, setTodaySteps] = useState(0);
  const [dailySummary, setDailySummary] = useState<any>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      // Get motivation
      const motivationRes = await api.get('/motivation');
      setMotivation(motivationRes.data.motivation);

      if (profile?.id) {
        // Get today's steps
        const today = new Date().toISOString().split('T')[0];
        const stepsRes = await api.get(`/steps/${profile.id}?date=${today}`);
        setTodaySteps(stepsRes.data.steps || 0);

        // Get daily nutrition summary
        const summaryRes = await api.get(`/food/daily-summary/${profile.id}/${today}`);
        setDailySummary(summaryRes.data);
      }
    } catch (error) {
      console.log('Error loading home data:', error);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  };

  const macros = profile?.calculated_macros;

  const quickActions = [
    {
      icon: 'barbell',
      title: 'Create Workout',
      subtitle: 'AI-powered program',
      color: '#FF6B6B',
      onPress: () => router.push('/workout-questionnaire'),
    },
    {
      icon: 'restaurant',
      title: 'Create Meal Plan',
      subtitle: 'Personalized meals',
      color: '#4ECDC4',
      onPress: () => router.push('/meal-questionnaire'),
    },
    {
      icon: 'camera',
      title: 'Log Food',
      subtitle: 'Snap & track',
      color: '#45B7D1',
      onPress: () => router.push('/food-log'),
    },
    {
      icon: 'body',
      title: 'Body Analyzer',
      subtitle: 'Track progress',
      color: '#9B59B6',
      onPress: () => router.push('/body-analyzer'),
    },
    {
      icon: 'chatbubble-ellipses',
      title: 'Ask InterFitAI',
      subtitle: 'Get answers',
      color: '#96CEB4',
      onPress: () => router.push('/(tabs)/ask-ai'),
    },
  ];

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />
        }
      >
        {/* Header */}
        <View style={styles.header}>
          <View>
            <Text style={styles.greeting}>Welcome back,</Text>
            <Text style={styles.name}>{profile?.name || 'Champion'}</Text>
          </View>
          <TouchableOpacity
            style={styles.subscriptionBadge}
            onPress={() => router.push('/subscription')}
          >
            <Ionicons name="diamond" size={16} color={colors.primary} />
            <Text style={styles.subscriptionText}>
              {profile?.subscription_status === 'free' ? 'Upgrade' : 'Premium'}
            </Text>
          </TouchableOpacity>
        </View>

        {/* Motivation */}
        {motivation && profile?.motivation_enabled && (
          <View style={styles.motivationCard}>
            <Ionicons name="flash" size={20} color={colors.primary} />
            <Text style={styles.motivationText}>{motivation}</Text>
          </View>
        )}

        {/* Macros Overview */}
        {macros && (
          <View style={styles.macrosCard}>
            <Text style={styles.sectionTitle}>Your Daily Targets</Text>
            <View style={styles.macrosGrid}>
              <View style={styles.macroItem}>
                <Text style={styles.macroValue}>{macros.calories}</Text>
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
          </View>
        )}

        {/* Today's Progress */}
        <View style={styles.progressCard}>
          <Text style={styles.sectionTitle}>Today's Progress</Text>
          <View style={styles.progressRow}>
            <View style={styles.progressItem}>
              <Ionicons name="footsteps" size={24} color={colors.primary} />
              <Text style={styles.progressValue}>{todaySteps.toLocaleString()}</Text>
              <Text style={styles.progressLabel}>Steps</Text>
            </View>
            <View style={styles.progressItem}>
              <Ionicons name="flame" size={24} color="#FF6B6B" />
              <Text style={styles.progressValue}>
                {dailySummary?.consumed?.calories || 0}
              </Text>
              <Text style={styles.progressLabel}>Calories</Text>
            </View>
            <View style={styles.progressItem}>
              <Ionicons name="water" size={24} color="#45B7D1" />
              <Text style={styles.progressValue}>
                {Math.round(dailySummary?.consumed?.protein || 0)}g
              </Text>
              <Text style={styles.progressLabel}>Protein</Text>
            </View>
          </View>
        </View>

        {/* Quick Actions */}
        <Text style={styles.sectionTitle}>Quick Actions</Text>
        <View style={styles.actionsGrid}>
          {quickActions.map((action, index) => (
            <TouchableOpacity
              key={index}
              style={styles.actionCard}
              onPress={action.onPress}
            >
              <View style={[styles.actionIcon, { backgroundColor: action.color + '20' }]}>
                <Ionicons name={action.icon as any} size={24} color={action.color} />
              </View>
              <Text style={styles.actionTitle}>{action.title}</Text>
              <Text style={styles.actionSubtitle}>{action.subtitle}</Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Steps Goal */}
        <TouchableOpacity
          style={styles.stepsCard}
          onPress={() => router.push('/(tabs)/profile')}
        >
          <View style={styles.stepsHeader}>
            <Ionicons name="footsteps" size={24} color={colors.primary} />
            <Text style={styles.stepsTitle}>Daily Steps</Text>
          </View>
          <View style={styles.stepsProgress}>
            <View style={styles.stepsBarBg}>
              <View
                style={[
                  styles.stepsBarFill,
                  { width: `${Math.min((todaySteps / 10000) * 100, 100)}%` },
                ]}
              />
            </View>
            <Text style={styles.stepsText}>{todaySteps.toLocaleString()} / 10,000</Text>
          </View>
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
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 20,
  },
  greeting: {
    fontSize: 14,
    color: colors.textSecondary,
  },
  name: {
    fontSize: 28,
    fontWeight: '700',
    color: colors.text,
  },
  subscriptionBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.primary + '20',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 20,
    gap: 4,
  },
  subscriptionText: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.primary,
  },
  motivationCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    padding: 16,
    borderRadius: 12,
    marginBottom: 20,
    gap: 12,
    borderLeftWidth: 3,
    borderLeftColor: colors.primary,
  },
  motivationText: {
    flex: 1,
    fontSize: 14,
    color: colors.text,
    lineHeight: 20,
  },
  macrosCard: {
    backgroundColor: colors.surface,
    padding: 20,
    borderRadius: 16,
    marginBottom: 20,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '700',
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
    fontSize: 24,
    fontWeight: '700',
    color: colors.primary,
  },
  macroLabel: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 4,
  },
  progressCard: {
    backgroundColor: colors.surface,
    padding: 20,
    borderRadius: 16,
    marginBottom: 20,
  },
  progressRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
  },
  progressItem: {
    alignItems: 'center',
  },
  progressValue: {
    fontSize: 20,
    fontWeight: '700',
    color: colors.text,
    marginTop: 8,
  },
  progressLabel: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 4,
  },
  actionsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
    marginBottom: 20,
  },
  actionCard: {
    width: '48%',
    backgroundColor: colors.surface,
    padding: 16,
    borderRadius: 16,
    alignItems: 'center',
  },
  actionIcon: {
    width: 48,
    height: 48,
    borderRadius: 24,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 12,
  },
  actionTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.text,
    textAlign: 'center',
  },
  actionSubtitle: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 4,
  },
  stepsCard: {
    backgroundColor: colors.surface,
    padding: 20,
    borderRadius: 16,
  },
  stepsHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 12,
  },
  stepsTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
  stepsProgress: {
    gap: 8,
  },
  stepsBarBg: {
    height: 8,
    backgroundColor: colors.surfaceLight,
    borderRadius: 4,
    overflow: 'hidden',
  },
  stepsBarFill: {
    height: '100%',
    backgroundColor: colors.primary,
    borderRadius: 4,
  },
  stepsText: {
    fontSize: 14,
    color: colors.textSecondary,
    textAlign: 'right',
  },
});