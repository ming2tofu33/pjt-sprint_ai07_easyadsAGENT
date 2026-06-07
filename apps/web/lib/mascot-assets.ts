export const mascotAssets = {
  homeReady: {
    src: "/mascots/home-ready.png",
    width: 615,
    height: 640
  },
  search: {
    src: "/mascots/search.png",
    width: 556,
    height: 640
  },
  referenceSearch: {
    src: "/mascots/reference-search.png",
    width: 640,
    height: 548
  },
  uploadCloud: {
    src: "/mascots/upload-cloud.png",
    width: 640,
    height: 545
  },
  uploadFile: {
    src: "/mascots/upload-file.png",
    width: 640,
    height: 618
  },
  generatingWait: {
    src: "/mascots/generating-wait.png",
    width: 640,
    height: 595
  },
  completeGift: {
    src: "/mascots/complete-gift.png",
    width: 640,
    height: 631
  },
  completeCheck: {
    src: "/mascots/complete-check.png",
    width: 640,
    height: 583
  },
  errorWorried: {
    src: "/mascots/error-worried.png",
    width: 615,
    height: 640
  },
  errorStressed: {
    src: "/mascots/error-stressed.png",
    width: 601,
    height: 640
  },
  brandShield: {
    src: "/mascots/brand-shield.png",
    width: 640,
    height: 583
  },
  brandSettings: {
    src: "/mascots/brand-settings.png",
    width: 640,
    height: 629
  },
  notificationBell: {
    src: "/mascots/notification-bell.png",
    width: 640,
    height: 554
  },
  notificationLetter: {
    src: "/mascots/notification-letter.png",
    width: 590,
    height: 640
  },
  archiveEmpty: {
    src: "/mascots/archive-empty.png",
    width: 569,
    height: 640
  },
  saveComplete: {
    src: "/mascots/save-complete.png",
    width: 640,
    height: 631
  },
  downloadFile: {
    src: "/mascots/sheet4-01-download-file.png",
    width: 631,
    height: 640
  },
  archiveBox: {
    src: "/mascots/sheet2-03-box-open.png",
    width: 609,
    height: 640
  },
  saveGift: {
    src: "/mascots/sheet5-05-gift.png",
    width: 640,
    height: 631
  },
  copyEmpty: {
    src: "/mascots/copy-empty.png",
    width: 633,
    height: 640
  },
  chatWave: {
    src: "/mascots/sheet5-06-chat-wave.png",
    width: 640,
    height: 577
  },
  questionPaper: {
    src: "/mascots/sheet3-02-question-paper.png",
    width: 633,
    height: 640
  },
  checkPaper: {
    src: "/mascots/sheet3-03-check-paper.png",
    width: 640,
    height: 583
  },
  settingsHelper: {
    src: "/mascots/sheet5-02-settings.png",
    width: 640,
    height: 629
  },
  bellHelper: {
    src: "/mascots/sheet5-03-bell.png",
    width: 640,
    height: 554
  },
  usageWaiting: {
    src: "/mascots/sheet2-02-waiting.png",
    width: 640,
    height: 595
  },
  cloudUpload: {
    src: "/mascots/sheet5-04-cloud-upload.png",
    width: 640,
    height: 545
  }
} as const;

export type MascotRole = keyof typeof mascotAssets;
