import React, { useEffect, useState, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  Image,
  Modal,
  Animated,
  Dimensions,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Pedometer } from 'expo-sensors';
import { GestureDetector, Gesture } from 'react-native-gesture-handler';
import ReanimatedModule, { useSharedValue, useAnimatedStyle, withSpring } from 'react-native-reanimated';
import { useUserStore } from '../../src/store/userStore';
import { colors } from '../../src/theme/colors';
import api from '../../src/services/api';

const { width: SCREEN_WIDTH, height: SCREEN_HEIGHT } = Dimensions.get('window');

export default function HomeScreen() {
  const router = useRouter();
  const { profile } = useUserStore();
  const [refreshing, setRefreshing] = useState(false);
  const [motivation, setMotivation] = useState('');
  const [todaySteps, setTodaySteps] = useState(0);
  const [dailySummary, setDailySummary] = useState<any>(null);
  const [showProfilePicture, setShowProfilePicture] = useState(false);
  const [imageScale] = useState(new Animated.Value(0.8));
  
  // Pinch-to-zoom and pan with Reanimated
  const scale = useSharedValue(1);
  const savedScale = useSharedValue(1);
  const translateX = useSharedValue(0);
  const translateY = useSharedValue(0);
  const savedTranslateX = useSharedValue(0);
  const savedTranslateY = useSharedValue(0);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      // Get motivation
      const motivationRes = await api.get('/motivation');
      setMotivation(motivationRes.data.motivation);

      // Get steps from device pedometer (same as profile tab)
      try {
        const available = await Pedometer.isAvailableAsync();
        if (available) {
          const end = new Date();
          const start = new Date();
          start.setHours(0, 0, 0, 0);
          const result = await Pedometer.getStepCountAsync(start, end);
          if (result) {
            setTodaySteps(result.steps);
          }
        }
      } catch (stepError) {
        console.log('Pedometer not available:', stepError);
      }

      if (profile?.id) {
        // Get daily nutrition summary
        const today = new Date().toISOString().split('T')[0];
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

  // Profile picture modal functions
  const openProfilePicture = () => {
    setShowProfilePicture(true);
    Animated.spring(imageScale, {
      toValue: 1,
      friction: 6,
      tension: 100,
      useNativeDriver: true,
    }).start();
  };

  const closeProfilePicture = () => {
    Animated.timing(imageScale, {
      toValue: 0.8,
      duration: 150,
      useNativeDriver: true,
    }).start(() => {
      setShowProfilePicture(false);
      // Reset all transforms
      scale.value = 1;
      savedScale.value = 1;
      translateX.value = 0;
      translateY.value = 0;
      savedTranslateX.value = 0;
      savedTranslateY.value = 0;
    });
  };

  // Instagram-style pinch gesture
  const pinchGesture = Gesture.Pinch()
    .onUpdate((event) => {
      scale.value = Math.min(Math.max(savedScale.value * event.scale, 1), 4);
    })
    .onEnd(() => {
      savedScale.value = scale.value;
      // Spring back if zoomed out and reset position
      if (scale.value <= 1) {
        scale.value = withSpring(1);
        savedScale.value = 1;
        translateX.value = withSpring(0);
        translateY.value = withSpring(0);
        savedTranslateX.value = 0;
        savedTranslateY.value = 0;
      }
    });

  // Pan gesture for dragging (only when zoomed)
  const panGesture = Gesture.Pan()
    .onUpdate((event) => {
      if (scale.value > 1) {
        translateX.value = savedTranslateX.value + event.translationX;
        translateY.value = savedTranslateY.value + event.translationY;
      }
    })
    .onEnd(() => {
      savedTranslateX.value = translateX.value;
      savedTranslateY.value = translateY.value;
    });

  // Double tap to zoom
  const doubleTapGesture = Gesture.Tap()
    .numberOfTaps(2)
    .onEnd(() => {
      if (scale.value > 1) {
        scale.value = withSpring(1);
        savedScale.value = 1;
        translateX.value = withSpring(0);
        translateY.value = withSpring(0);
        savedTranslateX.value = 0;
        savedTranslateY.value = 0;
      } else {
        scale.value = withSpring(2);
        savedScale.value = 2;
      }
    });

  const composedGesture = Gesture.Simultaneous(pinchGesture, panGesture, doubleTapGesture);

  const animatedImageStyle = useAnimatedStyle(() => ({
    transform: [
      { translateX: translateX.value },
      { translateY: translateY.value },
      { scale: scale.value }
    ],
  }));

  const macros = profile?.calculated_macros;

  const quickActions = [
    {
      icon: 'barbell',
      title: 'Workouts',
      subtitle: 'AI-powered programs',
      color: '#FF6B6B',
      onPress: () => router.push('/workout-questionnaire'),
    },
    {
      icon: 'restaurant',
      title: 'Meal Plans',
      subtitle: 'Personalized nutrition',
      color: '#4ECDC4',
      onPress: () => router.push('/meal-questionnaire'),
    },
    {
      icon: 'camera',
      title: 'Food Log',
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
      subtitle: 'Get AI answers',
      color: '#96CEB4',
      onPress: () => router.push('/(tabs)/ask-ai'),
    },
    {
      icon: 'footsteps',
      title: 'Daily Steps',
      subtitle: `${todaySteps.toLocaleString()} steps`,
      color: colors.primary,
      onPress: () => router.push('/(tabs)/profile'),
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
        {/* Logo Header */}
        <View style={styles.logoHeader}>
          <Image
            source={require('../../assets/logo-icon-yellow.png')}
            style={styles.logo}
            resizeMode="contain"
          />
          <View style={styles.headerRightActions}>
            <TouchableOpacity
              style={styles.settingsBtn}
              onPress={() => router.push('/settings')}
            >
              <Ionicons name="settings-outline" size={22} color={colors.text} />
            </TouchableOpacity>
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
        </View>

        {/* Welcome Section */}
        <View style={styles.welcomeSection}>
          <View style={styles.welcomeRow}>
            <TouchableOpacity 
              onPress={profile?.profile_image ? openProfilePicture : undefined}
              activeOpacity={profile?.profile_image ? 0.8 : 1}
              style={styles.avatarTouchable}
            >
              {profile?.profile_image ? (
                <View style={styles.avatarRing}>
                  <Image
                    source={{ uri: `data:image/jpeg;base64,${profile.profile_image}` }}
                    style={styles.welcomeAvatar}
                  />
                </View>
              ) : (
                <View style={styles.welcomeAvatarPlaceholder}>
                  <Ionicons name="person" size={24} color={colors.primary} />
                </View>
              )}
            </TouchableOpacity>
            <View>
              <Text style={styles.greeting}>Welcome back,</Text>
              <Text style={styles.name}>{profile?.name || 'Champion'}</Text>
            </View>
          </View>
        </View>

        {/* Profile Picture Modal - Instagram Style */}
        <Modal
          visible={showProfilePicture}
          transparent
          animationType="fade"
          onRequestClose={closeProfilePicture}
        >
          <TouchableOpacity
            style={styles.profilePictureModal}
            activeOpacity={1}
            onPress={closeProfilePicture}
          >
            <View style={styles.profilePictureHeader}>
              <View style={styles.profilePictureUserInfo}>
                <Text style={styles.profilePictureUsername}>{profile?.name || 'User'}</Text>
              </View>
              <TouchableOpacity onPress={closeProfilePicture} style={styles.profilePictureClose}>
                <Ionicons name="close" size={28} color={colors.text} />
              </TouchableOpacity>
            </View>
            
            <GestureDetector gesture={composedGesture}>
              <ReanimatedModule.View style={[styles.profilePictureContainer, animatedImageStyle]}>
                {profile?.profile_image && (
                  <Image
                    source={{ uri: `data:image/jpeg;base64,${profile.profile_image}` }}
                    style={styles.profilePictureLarge}
                    resizeMode="cover"
                  />
                )}
              </ReanimatedModule.View>
            </GestureDetector>
          </TouchableOpacity>
        </Modal>

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
                <Text style={styles.macroValue}>
                  {(macros.calories || 0) + (profile?.calorie_adjustment || 0)}
                </Text>
                <Text style={styles.macroLabel}>Calories</Text>
              </View>
              <View style={styles.macroItem}>
                <Text style={[styles.macroValue, { color: '#FF6B6B' }]}>{macros.protein}g</Text>
                <Text style={styles.macroLabel}>Protein</Text>
              </View>
              <View style={styles.macroItem}>
                <Text style={[styles.macroValue, { color: '#4ECDC4' }]}>
                  {Math.round((macros.carbs || 0) + ((profile?.calorie_adjustment || 0) / 4))}g
                </Text>
                <Text style={styles.macroLabel}>Carbs</Text>
              </View>
              <View style={styles.macroItem}>
                <Text style={[styles.macroValue, { color: '#F97316' }]}>{macros.fats}g</Text>
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

        {/* Quick Actions - 6 Item Grid */}
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
  logoHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  logo: {
    width: 50,
    height: 50,
  },
  welcomeSection: {
    marginBottom: 20,
  },
  welcomeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  welcomeAvatar: {
    width: 50,
    height: 50,
    borderRadius: 25,
  },
  welcomeAvatarPlaceholder: {
    width: 50,
    height: 50,
    borderRadius: 25,
    backgroundColor: colors.primary + '20',
    justifyContent: 'center',
    alignItems: 'center',
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
  headerRightActions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  settingsBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.surface,
    justifyContent: 'center',
    alignItems: 'center',
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
    justifyContent: 'space-between',
    gap: 12,
    marginBottom: 20,
  },
  actionCard: {
    width: '47%',
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
    textAlign: 'center',
  },
  // Profile Picture Modal Styles
  avatarTouchable: {
    position: 'relative',
  },
  avatarRing: {
    width: 54,
    height: 54,
    borderRadius: 27,
    borderWidth: 2,
    borderColor: colors.primary,
    padding: 2,
    justifyContent: 'center',
    alignItems: 'center',
  },
  profilePictureModal: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.95)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  profilePictureHeader: {
    position: 'absolute',
    top: 50,
    left: 0,
    right: 0,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
  },
  profilePictureUserInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  profilePictureUsername: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
  profilePictureClose: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.surface,
    justifyContent: 'center',
    alignItems: 'center',
  },
  profilePictureContainer: {
    width: SCREEN_WIDTH * 0.85,
    height: SCREEN_WIDTH * 0.85,
    borderRadius: (SCREEN_WIDTH * 0.85) / 2,
    overflow: 'hidden',
    backgroundColor: colors.surface,
    borderWidth: 3,
    borderColor: colors.primary,
  },
  profilePictureLarge: {
    width: '100%',
    height: '100%',
  },
});