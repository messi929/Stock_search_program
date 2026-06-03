"use client";

/**
 * Firebase Auth 사용자 액션 — 구글 로그인, 카카오 로그인(custom token), 로그아웃.
 *
 * 카카오는 Firebase native 미지원 → 백엔드(/api/auth/kakao)가 카카오 인가코드를
 * Firebase Custom Token으로 교환하고, 프론트가 signInWithCustomToken으로 로그인.
 */
import {
  createUserWithEmailAndPassword,
  GoogleAuthProvider,
  sendEmailVerification,
  sendPasswordResetEmail,
  signInWithCustomToken,
  signInWithEmailAndPassword,
  signInWithPopup,
  signOut as fbSignOut,
} from "firebase/auth";

import { apiCall } from "./api";
import { auth } from "./firebase";

const googleProvider = new GoogleAuthProvider();

export async function signInWithGoogle() {
  return signInWithPopup(auth, googleProvider);
}

export async function signOut() {
  return fbSignOut(auth);
}

// ── 이메일/비밀번호 ──────────────────────────────────────────────────────────
// 어뷰징 방어: 가입 직후 인증 메일 발송 → 인증 전에는 트라이얼 불가(백엔드
// start-trial이 email_verified 요구). 일회용 메일은 백엔드 trial 단계에서도 차단.

/** 일회용 메일 힌트 — 가입 폼에서 사전 경고용(우회 가능, 본 차단은 백엔드). */
const DISPOSABLE_HINT =
  /(tempmail|temp-mail|10minute|guerrilla|mailinator|throwaway|trashmail|yopmail|maildrop|sharklasers|getnada|1secmail|mail\.tm|dispostable|fakeinbox|moakt|emailfake|mailpoof)/i;

export function looksDisposable(email: string): boolean {
  const domain = (email.split("@")[1] || "").toLowerCase();
  return !!domain && DISPOSABLE_HINT.test(domain);
}

/** 회원가입 — 계정 생성 + 인증 메일 발송. */
export async function signUpWithEmail(email: string, password: string) {
  const cred = await createUserWithEmailAndPassword(auth, email, password);
  try {
    await sendEmailVerification(cred.user);
  } catch (e) {
    console.warn("[auth] sendEmailVerification 실패:", e);
  }
  return cred;
}

export async function signInWithEmail(email: string, password: string) {
  return signInWithEmailAndPassword(auth, email, password);
}

export async function sendPasswordReset(email: string) {
  return sendPasswordResetEmail(auth, email);
}

/** 미인증 사용자에게 인증 메일 재발송. */
export async function resendVerification() {
  if (auth.currentUser && !auth.currentUser.emailVerified) {
    return sendEmailVerification(auth.currentUser);
  }
}

// ── 카카오 ─────────────────────────────────────────────────────────────────
// REST API 키는 공개 가능(프론트 노출 OK). client secret은 백엔드 전용.
const KAKAO_REST_KEY = process.env.NEXT_PUBLIC_KAKAO_REST_API_KEY;

/** 카카오 로그인 활성화 여부 (env 키 주입 시에만 버튼 활성). */
export function kakaoConfigured(): boolean {
  return !!KAKAO_REST_KEY;
}

/** 카카오 콘솔에 등록해야 하는 Redirect URI와 동일해야 함. */
function kakaoRedirectUri(): string {
  return `${window.location.origin}/login/kakao/callback`;
}

/**
 * 카카오 인가 페이지로 이동. 로그인 후 돌아올 경로(next)는 state로 전달.
 */
export function startKakaoLogin(next?: string): void {
  if (!KAKAO_REST_KEY) return;
  const params = new URLSearchParams({
    response_type: "code",
    client_id: KAKAO_REST_KEY,
    redirect_uri: kakaoRedirectUri(),
  });
  if (next) params.set("state", next);
  window.location.href = `https://kauth.kakao.com/oauth/authorize?${params.toString()}`;
}

/**
 * 콜백 페이지에서 호출 — 인가코드를 백엔드에 넘겨 custom token을 받고 로그인.
 * redirect_uri는 인가 요청 때와 byte 단위로 동일해야 카카오가 승인.
 */
export async function completeKakaoLogin(code: string) {
  const res = await apiCall<{ token: string }>("/api/auth/kakao", {
    method: "POST",
    body: JSON.stringify({ code, redirect_uri: kakaoRedirectUri() }),
  });
  return signInWithCustomToken(auth, res.token);
}
