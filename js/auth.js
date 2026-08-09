import { auth } from './firebase.js';
import { AppState, triggerCloudSync } from './storage.js';

export function getInternalEmail(rollNumber) {
  return `${rollNumber}@student.app`;
}

export async function loginUser(rollNumber, password) {
  const email = getInternalEmail(rollNumber);
  try {
    const userCredential = await auth.signInWithEmailAndPassword(email, password);
    return { success: true, user: userCredential.user };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

export async function signupUser(name, rollNumber, password) {
  const email = getInternalEmail(rollNumber);
  try {
    const userCredential = await auth.createUserWithEmailAndPassword(email, password);
    AppState.profile = {
      name: name,
      rollNumber: rollNumber,
      createdAt: new Date().toISOString()
    };
    triggerCloudSync();
    return { success: true, user: userCredential.user };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

export async function logoutUser() {
  if (auth.currentUser) {
    localStorage.removeItem(`app_state_${auth.currentUser.uid}`);
  }
  await auth.signOut();
  window.location.reload();
}
