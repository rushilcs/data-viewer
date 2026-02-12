"use client";

import Link from "next/link";
import { motion } from "framer-motion";

const headline = "Verita Dataset Viewer";
const underlineWord = "Verita";
const subtitle = "Curate, view, and share data in one place.";

export default function LandingPage() {
  const words = headline.split(" ");
  let charIndex = 0;

  return (
    <div className="relative min-h-screen overflow-hidden bg-slate-50 text-slate-800">
      {/* Subtle grain overlay */}
      <div
        className="pointer-events-none fixed inset-0 z-10 opacity-[0.02]"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E")`,
        }}
      />

      {/* Animated gradient orbs */}
      <div className="fixed inset-0 overflow-hidden">
        <motion.div
          className="absolute -left-40 -top-40 h-[500px] w-[500px] rounded-full bg-teal-400/25 blur-[120px]"
          animate={{
            x: [0, 30, 0],
            y: [0, -20, 0],
          }}
          transition={{ duration: 20, repeat: Infinity, ease: "easeInOut" }}
        />
        <motion.div
          className="absolute -bottom-40 -right-40 h-[500px] w-[500px] rounded-full bg-cyan-400/20 blur-[120px]"
          animate={{
            x: [0, -25, 0],
            y: [0, 30, 0],
          }}
          transition={{ duration: 22, repeat: Infinity, ease: "easeInOut" }}
        />
        <motion.div
          className="absolute left-1/2 top-1/2 h-[300px] w-[300px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-violet-400/15 blur-[100px]"
          animate={{
            scale: [1, 1.1, 1],
            opacity: [0.5, 0.8, 0.5],
          }}
          transition={{ duration: 15, repeat: Infinity, ease: "easeInOut" }}
        />
      </div>

      <div className="relative z-20 flex min-h-screen flex-col items-center justify-center px-6 py-16">
        <motion.div
          className="max-w-4xl text-center"
          initial="hidden"
          animate="visible"
          variants={{
            visible: {
              transition: { staggerChildren: 0.03, delayChildren: 0.2 },
            },
            hidden: {},
          }}
        >
          <h1 className="flex flex-wrap justify-center gap-x-2 gap-y-1 text-[clamp(2.5rem,8vw,5rem)] font-semibold leading-tight tracking-tight">
            {words.map((word, wi) => (
              <span key={wi} className="inline-flex">
                {word === underlineWord ? (
                  <span className="relative inline-flex">
                    {word.split("").map((letter, li) => (
                      <motion.span
                        key={li}
                        className="inline-block"
                        variants={{
                          hidden: { opacity: 0, y: 24 },
                          visible: { opacity: 1, y: 0 },
                        }}
                        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
                      >
                        {letter}
                      </motion.span>
                    ))}
                    <motion.span
                      className="absolute bottom-0 left-0 h-0.5 bg-teal-500"
                      initial={{ width: 0 }}
                      animate={{ width: "100%" }}
                      transition={{ delay: 1.2, duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
                    />
                  </span>
                ) : (
                  word.split("").map((letter, li) => (
                    <motion.span
                      key={li}
                      className="inline-block"
                      variants={{
                        hidden: { opacity: 0, y: 24 },
                        visible: { opacity: 1, y: 0 },
                      }}
                      transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
                    >
                      {letter}
                    </motion.span>
                  ))
                )}
              </span>
            ))}
          </h1>

          <motion.p
            className="mx-auto mt-8 max-w-xl text-lg text-slate-600 sm:text-xl"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 1.1, duration: 0.6 }}
          >
            {subtitle}
          </motion.p>

          <motion.div
            className="mt-12 flex flex-col items-center gap-4 sm:flex-row sm:justify-center"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 1.5, duration: 0.5 }}
          >
            <Link href="/login" className="w-full sm:w-auto">
              <motion.span
                className="inline-block w-full rounded-2xl bg-teal-500 px-8 py-3.5 text-center font-medium text-white shadow-lg shadow-teal-500/30 transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-400"
                whileHover={{
                  boxShadow: "0 0 30px rgba(20, 184, 166, 0.4)",
                  scale: 1.02,
                }}
                whileTap={{ scale: 0.98 }}
              >
                Sign in
              </motion.span>
            </Link>
            <Link href="/signup" className="w-full sm:w-auto">
              <motion.span
                className="inline-block w-full rounded-2xl border-2 border-slate-200 bg-white px-8 py-3.5 text-center font-medium text-slate-700 shadow-sm transition hover:border-teal-300 hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-400"
                whileHover={{
                  borderColor: "rgb(94 234 212)",
                  scale: 1.02,
                }}
                whileTap={{ scale: 0.98 }}
              >
                Sign up
              </motion.span>
            </Link>
          </motion.div>

          {/* Scroll hint */}
          <motion.div
            className="mt-24 flex justify-center"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 2 }}
          >
            <motion.div
              className="rounded-full border-2 border-slate-200 p-2"
              animate={{ y: [0, 6, 0] }}
              transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
            >
              <svg
                className="h-5 w-5 text-slate-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M19 14l-7 7m0 0l-7-7m7 7V3"
                />
              </svg>
            </motion.div>
          </motion.div>
        </motion.div>
      </div>
    </div>
  );
}
