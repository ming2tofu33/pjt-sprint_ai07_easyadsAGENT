import React from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { BRAND_KIT_STORAGE_KEY } from "@/lib/brand-kit-storage";

const navigationMock = vi.hoisted(() => ({
  push: vi.fn(),
  back: vi.fn(),
  replace: vi.fn()
}));

const searchParamsMock = vi.hoisted(() => ({
  value: new URLSearchParams()
}));

vi.mock("@/lib/api-client", () => ({
  ApiError: class ApiError extends Error {
    errorCode?: string;
    status: number;

    constructor(message: string, options: { errorCode?: string; status: number }) {
      super(message);
      this.name = "ApiError";
      this.errorCode = options.errorCode;
      this.status = options.status;
    }
  },
  startChatGeneration: vi.fn(
    async (
      userInput: string,
      options?: { copyGenerationMode?: string; userCustomHeadline?: string; userCustomSubcopy?: string; selectedReferenceTemplateId?: string }
    ) => {
    if (options?.copyGenerationMode === "no_copy") {
      return {
        type: "brief_ready",
        jobId: "job_no_copy",
        threadId: "thread_no_copy",
        status: "done",
        context: {
          businessType: "카페",
          itemOrService: "딸기라떼",
          promotionGoal: "광고 홍보"
        },
        brief: {
          purpose: "광고 홍보",
          item: "딸기라떼",
          copy: "문구 없이 이미지로만",
          tone: "브랜드에 맞춘 분위기",
          channel: "인스타 피드 (1:1)",
          imageDirection: "딸기라떼 중심의 깔끔한 광고 배경과 문구 여백을 구성해요.",
          finalImagePath: "data/outputs/job_no_copy/final_composite.png"
        },
        copyGenerationMode: "no_copy"
      };
    }
    if (options?.copyGenerationMode === "auto_pilot") {
      return {
        type: "brief_ready",
        jobId: "job_auto_pilot",
        threadId: "thread_auto_pilot",
        status: "done",
        context: {
          businessType: "카페",
          itemOrService: "딸기라떼",
          promotionGoal: "신메뉴 출시"
        },
        brief: {
          purpose: "신메뉴 출시",
          item: "딸기라떼",
          copy: "AI가 고른 딸기라떼 한 잔",
          tone: "브랜드에 맞춘 분위기",
          channel: "인스타 피드 (1:1)",
          imageDirection: "딸기라떼 중심의 깔끔한 광고 배경과 문구 여백을 구성해요.",
          finalImagePath: "data/outputs/job_auto_pilot/final_composite.png"
        },
        copyGenerationMode: "auto_pilot"
      };
    }
    if (options?.copyGenerationMode === "custom_input") {
      return {
        type: "brief_ready",
        jobId: "job_custom_copy",
        threadId: "thread_custom_copy",
        status: "done",
        context: {
          businessType: "카페",
          itemOrService: "딸기라떼",
          promotionGoal: "신메뉴 출시"
        },
        brief: {
          purpose: "신메뉴 출시",
          item: "딸기라떼",
          copy: options.userCustomHeadline ?? "직접 입력한 문구",
          tone: "브랜드에 맞춘 분위기",
          channel: "인스타 피드 (1:1)",
          imageDirection: "딸기라떼 중심의 깔끔한 광고 배경과 문구 여백을 구성해요.",
          finalImagePath: "data/outputs/job_custom_copy/final_composite.png"
        },
        copyGenerationMode: "custom_input"
      };
    }
    if (userInput === "광고 만들어줘") {
      return {
        type: "option_question",
        jobId: "job_question",
        threadId: "thread_question",
        status: "waiting_user_selection",
        context: {},
        question: {
          field: "business_type",
          question: "어떤 업종의 광고인가요?",
          options: [
            { id: 1, label: "음식점/식당", value: "restaurant" },
            { id: 2, label: "카페/디저트", value: "cafe" },
            { id: 9, label: "직접 입력", value: "custom" }
          ]
        },
        missingFields: ["business_type"]
      };
    }

    if (userInput === "후보 없는 광고") {
      return {
        type: "copy_candidates",
        jobId: "job_empty",
        threadId: "thread_empty",
        status: "generating_copy_candidates",
        context: {
          businessType: "카페",
          itemOrService: "대표 메뉴",
          promotionGoal: "광고 홍보"
        },
        copyCandidates: [],
        recommendedCopyId: null
      };
    }

    return {
      type: "copy_candidates",
      jobId: "job_1",
      threadId: "thread_1",
      status: "generating_copy_candidates",
      context: {
        businessType: "카페",
        itemOrService: "딸기라떼",
        promotionGoal: "신메뉴 출시"
      },
      copyCandidates: [
        { id: "copy_1", headline: "봄을 닮은 한 잔, 딸기라떼 출시" },
        { id: "copy_2", headline: "오늘만 더 달콤하게, 신메뉴 딸기라떼" }
      ],
      recommendedCopyId: "copy_1",
      copyCandidateOrigin: "rule_based"
    };
  }),
  answerChatQuestion: vi.fn(async () => ({
    type: "copy_candidates",
    jobId: "job_question",
    threadId: "thread_question",
    status: "generating_copy_candidates",
    context: {
      businessType: "카페",
      itemOrService: "대표 메뉴",
      promotionGoal: "광고 홍보"
    },
    copyCandidates: [{ id: "copy_1", headline: "우리 가게 대표 메뉴를 알려요" }],
    recommendedCopyId: "copy_1",
    copyCandidateOrigin: "rule_based"
  })),
  createChatBrief: vi.fn(async () => ({
    jobId: "job_1",
    threadId: "thread_1",
    status: "done",
    brief: {
      purpose: "신메뉴 출시",
      item: "딸기라떼",
      copy: "봄을 닮은 한 잔, 딸기라떼 출시",
      tone: "상큼한 분위기",
      channel: "인스타 스토리 (9:16)",
      imageDirection: "상큼한 분위기를 살려 딸기라떼 중심의 깔끔한 광고 배경과 문구 여백을 구성해요.",
      finalImagePath: "data/outputs/job_1/final_composite.png"
    }
  })),
  uploadPhotoAsset: vi.fn(async () => ({
    sourceImagePath: "data/uploads/photo_1.png",
    fileName: "menu.png",
    mimeType: "image/png",
    sizeBytes: 3
  })),
  uploadReferenceAsset: vi.fn(async () => ({
    referenceImagePath: "data/uploads/reference_1.png",
    fileName: "reference.png",
    mimeType: "image/png",
    sizeBytes: 3
  })),
	  startPhotoGeneration: vi.fn(async (input?: { copyGenerationMode?: string; sourceImagePath?: string; userCustomHeadline?: string; userCustomSubcopy?: string }) => {
    if (input?.copyGenerationMode === "no_copy") {
      return {
        type: "brief_ready",
        jobId: "photo_no_copy",
        threadId: "photo_no_copy_thread",
        status: "done",
        context: {
          businessType: "카페",
          itemOrService: "딸기라떼",
          promotionGoal: "광고 홍보"
        },
        brief: {
          purpose: "광고 홍보",
          item: "딸기라떼",
          copy: "문구 없이 이미지로만",
          tone: "브랜드에 맞춘 분위기",
          channel: "인스타 피드 (1:1)",
          imageDirection: "딸기라떼 중심의 깔끔한 광고 배경과 문구 여백을 구성해요.",
          finalImagePath: "data/outputs/photo_no_copy/final_composite.png"
        },
        copyGenerationMode: "no_copy"
      };
    }
    if (input?.copyGenerationMode === "auto_pilot") {
      return {
        type: "brief_ready",
        jobId: "photo_auto_pilot",
        threadId: "photo_auto_pilot_thread",
        status: "done",
        context: {
          businessType: "카페",
          itemOrService: "딸기라떼",
          promotionGoal: "신메뉴 출시"
        },
        brief: {
          purpose: "신메뉴 출시",
          item: "딸기라떼",
          copy: "AI가 고른 딸기라떼 한 잔",
          tone: "브랜드에 맞춘 분위기",
          channel: "인스타 피드 (1:1)",
          imageDirection: "딸기라떼 중심의 깔끔한 광고 배경과 문구 여백을 구성해요.",
          finalImagePath: "data/outputs/photo_auto_pilot/final_composite.png"
        },
        copyGenerationMode: "auto_pilot"
      };
    }
    if (input?.copyGenerationMode === "custom_input") {
      return {
        type: "brief_ready",
        jobId: "photo_custom_copy",
        threadId: "photo_custom_copy_thread",
        status: "done",
        context: {
          businessType: "카페",
          itemOrService: "딸기라떼",
          promotionGoal: "신메뉴 출시"
        },
        brief: {
          purpose: "신메뉴 출시",
          item: "딸기라떼",
          copy: input.userCustomHeadline ?? "직접 입력한 문구",
          tone: "브랜드에 맞춘 분위기",
          channel: "인스타 피드 (1:1)",
          imageDirection: "딸기라떼 중심의 깔끔한 광고 배경과 문구 여백을 구성해요.",
          finalImagePath: "data/outputs/photo_custom_copy/final_composite.png"
        },
        copyGenerationMode: "custom_input"
      };
    }
    return {
      type: "copy_candidates",
      jobId: "photo_1",
      threadId: "photo_1_thread",
      status: "generating_copy_candidates",
      context: {
        businessType: "카페",
        itemOrService: "딸기라떼",
        promotionGoal: "신메뉴 출시"
      },
      copyCandidates: [{ id: "copy_photo_1", headline: "사진 속 메뉴를 오늘의 신메뉴로" }],
	      recommendedCopyId: "copy_photo_1"
	    };
	  }),
	  createGenerationJob: vi.fn(async (payload: Record<string, unknown>) => {
    const metadata = typeof payload.metadata === "object" && payload.metadata ? (payload.metadata as Record<string, unknown>) : {};
    const threadId = typeof payload.threadId === "string" ? payload.threadId : "thread_1";
    const userInput = String(payload.userInput ?? "");
    const copyGenerationMode = typeof payload.copyGenerationMode === "string" ? payload.copyGenerationMode : "suggest_candidates";
    const context = {
      businessType: "카페",
      itemOrService: userInput.includes("후보 없는 광고") ? "대표 메뉴" : "딸기라떼",
      promotionGoal: userInput.includes("광고 만들어줘") && !userInput.includes("신메뉴") ? "광고 홍보" : "신메뉴 출시"
    };

    if (metadata.source !== "web_generation_flow") {
      const briefFor = (input: {
        jobId: string;
        copy: string;
        finalImagePath: string;
        mode: string;
        purpose?: string;
      }) => ({
        success: true,
        job: {
          job_id: input.jobId,
          thread_id: threadId,
          status: "done",
          progress: { progress_percent: 100, current_stage: "completed" },
          result_payload: {
            context: { ...context, promotionGoal: input.purpose ?? context.promotionGoal },
            brief: {
              purpose: input.purpose ?? context.promotionGoal,
              item: "딸기라떼",
              copy: input.copy,
              tone: "브랜드에 맞춘 분위기",
              channel: "인스타 피드 (1:1)",
              imageDirection: "딸기라떼 중심의 깔끔한 광고 배경과 문구 여백을 구성해요.",
              finalImagePath: input.finalImagePath
            },
            copyGenerationMode: input.mode
          },
          metadata: {},
          created_at: "2026-06-05T00:00:00.000Z",
          updated_at: "2026-06-05T00:00:00.000Z"
        }
      });

      if (copyGenerationMode === "no_copy") {
        return briefFor({
          jobId: "job_no_copy",
          copy: "문구 없이 이미지로만",
          finalImagePath: "data/outputs/job_no_copy/final_composite.png",
          mode: "no_copy",
          purpose: "광고 홍보"
        });
      }

      if (copyGenerationMode === "auto_pilot") {
        return briefFor({
          jobId: "job_auto_pilot",
          copy: "AI가 고른 딸기라떼 한 잔",
          finalImagePath: "data/outputs/job_auto_pilot/final_composite.png",
          mode: "auto_pilot"
        });
      }

      if (copyGenerationMode === "custom_input") {
        return briefFor({
          jobId: "job_custom_copy",
          copy: typeof payload.userCustomHeadline === "string" ? payload.userCustomHeadline : "직접 입력한 문구",
          finalImagePath: "data/outputs/job_custom_copy/final_composite.png",
          mode: "custom_input"
        });
      }

      if (userInput.startsWith("광고 만들어줘")) {
        return {
          success: true,
          job: {
            job_id: "job_question",
            thread_id: "thread_question",
            status: "waiting_user_input",
            progress: { progress_percent: 35, current_stage: "waiting_user_input" },
            result_payload: {
              context: {},
              question: {
                field: "business_type",
                question: "어떤 업종의 광고인가요?",
                options: [
                  { id: 1, label: "음식점/식당", value: "restaurant" },
                  { id: 2, label: "카페/디저트", value: "cafe" },
                  { id: 9, label: "직접 입력", value: "custom" }
                ]
              },
              missingFields: ["business_type"]
            },
            metadata: {},
            created_at: "2026-06-05T00:00:00.000Z",
            updated_at: "2026-06-05T00:00:00.000Z"
          }
        };
      }

      if (userInput.includes("원육 세일")) {
        return {
          success: true,
          job: {
            job_id: "job_reference_context_question",
            thread_id: threadId,
            status: "waiting_user_input",
            progress: { progress_percent: 50, current_stage: "waiting_user_input" },
            result_payload: {
              business_type: "restaurant",
              promotion_goal: "discount_event",
              missing_fields: ["item_or_service"],
              option_question: {
                field: "item_or_service",
                question: "홍보할 상품이나 서비스는 무엇인가요?",
                options: [
                  { id: 1, label: "대표 메뉴", value: "signature_item" },
                  { id: 2, label: "신상품", value: "new_item" },
                  { id: 3, label: "직접 입력", value: "custom" }
                ]
              }
            },
            metadata: {},
            created_at: "2026-06-05T00:00:00.000Z",
            updated_at: "2026-06-05T00:00:00.000Z"
          }
        };
      }

      if (userInput.includes("후보 없는 광고")) {
        return {
          success: true,
          job: {
            job_id: "job_empty",
            thread_id: "thread_empty",
            status: "done",
            progress: { progress_percent: 100, current_stage: "completed" },
            result_payload: {
              type: "copy_candidates",
              context,
              copyCandidates: [],
              recommendedCopyId: null
            },
            metadata: {},
            created_at: "2026-06-05T00:00:00.000Z",
            updated_at: "2026-06-05T00:00:00.000Z"
          }
        };
      }

      return {
        success: true,
        job: {
          job_id: "job_1",
          thread_id: threadId,
          status: "done",
          progress: { progress_percent: 100, current_stage: "completed" },
          result_payload: {
            type: "copy_candidates",
            context,
            copyCandidates: [
              { id: "copy_1", headline: "봄을 닮은 한 잔, 딸기라떼 출시" },
              { id: "copy_2", headline: "오늘만 더 달콤하게, 신메뉴 딸기라떼" }
            ],
            recommendedCopyId: "copy_1",
            copyCandidateOrigin: "rule_based",
            copyGenerationMode
          },
          metadata: {},
          created_at: "2026-06-05T00:00:00.000Z",
          updated_at: "2026-06-05T00:00:00.000Z"
        }
      };
    }

    return {
	    success: true,
	    job: {
	      job_id: "generation_job_1",
	      thread_id: threadId,
	      status: "done",
	      progress: {
	        progress_percent: 100,
	        current_stage: "completed"
	      },
	      result_payload: {
	        schema_version: "result_artifact_v1",
	        job_id: "generation_job_1",
	        preview_image_url: "/api/generated-assets?path=data%2Foutputs%2Fgeneration_job_1%2Ffinal_0.png",
	        download_url: "/api/generated-assets?path=data%2Foutputs%2Fgeneration_job_1%2Ffinal_0.png",
	        final_image_path: "data/outputs/generation_job_1/final_0.png",
	        engine:
	          "requested_engine" in metadata
	            ? String(metadata.requested_engine)
	            : "gpt_image_1"
	      },
	      metadata: {
	        selected_engine_label:
	          "selected_engine_label" in metadata
	            ? metadata.selected_engine_label
	            : "GPT-image-1"
	      },
	      created_at: "2026-06-05T00:00:00.000Z",
	      updated_at: "2026-06-05T00:00:00.000Z"
	    }
    };
	  }),
	  getGenerationJob: vi.fn(async () => ({
	    success: true,
	    job: {
	      job_id: "generation_job_1",
	      thread_id: "thread_1",
	      status: "done",
	      progress: {
	        progress_percent: 100,
	        current_stage: "completed"
	      },
	      result_payload: {
	        schema_version: "result_artifact_v1",
	        job_id: "generation_job_1",
	        preview_image_url: "/api/generated-assets?path=data%2Foutputs%2Fgeneration_job_1%2Ffinal_0.png",
	        download_url: "/api/generated-assets?path=data%2Foutputs%2Fgeneration_job_1%2Ffinal_0.png",
	        final_image_path: "data/outputs/generation_job_1/final_0.png",
	        engine: "gpt_image_1"
	      },
	      metadata: {
	        selected_engine_label: "GPT-image-1"
	      },
	      created_at: "2026-06-05T00:00:00.000Z",
	      updated_at: "2026-06-05T00:00:00.000Z"
	    }
	  })),
	  answerGenerationJob: vi.fn(async () => ({
	    success: true,
	    job: {
	      job_id: "generation_job_1",
	      thread_id: "thread_1",
	      status: "done",
	      progress: {
	        progress_percent: 100,
	        current_stage: "completed"
	      },
	      result_payload: {
	        schema_version: "result_artifact_v1",
	        job_id: "generation_job_1",
	        preview_image_url: "/api/generated-assets?path=data%2Foutputs%2Fgeneration_job_1%2Ffinal_0.png",
	        download_url: "/api/generated-assets?path=data%2Foutputs%2Fgeneration_job_1%2Ffinal_0.png",
	        final_image_path: "data/outputs/generation_job_1/final_0.png",
	        engine: "gpt_image_1"
	      },
	      metadata: {
	        selected_engine_label: "GPT-image-1"
	      },
	      created_at: "2026-06-05T00:00:00.000Z",
	      updated_at: "2026-06-05T00:00:00.000Z"
	    }
	  })),
	  listReferenceTemplates: vi.fn(async () => ({
    items: [
      {
        templateId: "temp_watermelon_juice_feed",
        title: "수박주스 블루 여름 피드",
        description: "파란 배경과 큼직한 음료 중심의 여름 음료 샘플",
        category: "cafe",
        tags: ["수박", "여름"],
        businessTypes: ["cafe"],
        adFormats: ["instagram_feed"],
        platforms: ["instagram"],
        aspectRatio: "4:3",
        thumbnailUrl: "http://127.0.0.1:4000/api/references/temp-assets/2026-06-user-refs/watermelon-juice.png",
        previewUrl: "http://127.0.0.1:4000/api/references/temp-assets/2026-06-user-refs/watermelon-juice.png",
        styleKeywords: ["summer", "blue"],
        colorPalette: ["#5AB4F2", "#EF3B3B", "#FFFFFF"],
        layoutHint: "top_large_headline_center_product_bottom_copy",
        typographyHint: "extra_bold_condensed_headline",
        popularityScore: 0.5,
        isSaved: false
      },
      {
        templateId: "seed_no_image_reference",
        title: "이미지 없는 seed 샘플",
        description: "이미지가 없는 내부 메타데이터",
        category: "cafe",
        tags: ["카페"],
        businessTypes: ["cafe"],
        adFormats: ["instagram_feed"],
        platforms: ["instagram"],
        aspectRatio: "1:1",
        thumbnailUrl: null,
        previewUrl: null,
        styleKeywords: ["mock"],
        colorPalette: ["#FFFFFF"],
        layoutHint: "placeholder",
        typographyHint: "placeholder",
        popularityScore: 0.9,
        isSaved: false
      }
    ],
    pagination: { limit: 40, offset: 0, total: 2, hasMore: false }
  })),
  saveArchiveItem: vi.fn(async () => ({
    item: {
      adId: "archive_1",
      jobId: "job_1",
      title: "봄을 닮은 한 잔, 딸기라떼 출시",
      imageUrl: "/api/generated-assets?path=data%2Foutputs%2Fjob_1%2Ffinal_composite.png",
      thumbnailUrl: "/api/generated-assets?path=data%2Foutputs%2Fjob_1%2Ffinal_composite.png",
      status: "saved",
      source: "generated",
      metadata: {}
    }
  })),
  listArchiveItems: vi.fn(async () => ({
    items: [],
    pagination: { limit: 50, offset: 0, total: 0, hasMore: false }
  })),
  getArchiveItem: vi.fn(async (archiveItemId: string) => ({
    adId: archiveItemId,
    jobId: "job_db_detail",
    outputId: "output_db_detail",
    title: "DB 상세 광고",
    imageUrl: null,
    thumbnailUrl: null,
    downloadUrl: "https://cdn.example.com/archive-db-detail.png",
    status: "saved",
    adFormat: "1:1",
    platform: "인스타 피드",
    source: "generated",
    storageProvider: "r2",
    mimeType: "image/png",
    width: 1200,
    height: 1200,
    savedAt: "2026-06-05T00:00:00+00:00",
    metadata: { fileName: "archive-db-detail.png", fileType: "PNG", tags: ["카페"] }
  })),
  listChatThreads: vi.fn(async () => ({
    success: true,
    threads: [],
    total: 0
  })),
  getChatThreadState: vi.fn(async () => ({
    success: true,
    snapshot: {
      snapshot_id: "snapshot_waiting",
      thread_id: "thread_waiting",
      job_id: "job_waiting",
      snapshot_version: 1,
      schema_version: 1,
      snapshot_kind: "waiting_user_input",
      state_payload: {
        user_input: "광고 만들어줘",
        business_type: "카페",
        pending_interrupt: {
          type: "option_question",
          option_question: {
            field: "item_or_service",
            question: "홍보할 상품이나 서비스는 무엇인가요?",
            options: [{ id: 1, label: "대표 메뉴", value: "signature_item" }]
          }
        }
      },
      changed_fields: [],
      reference_template_snapshot: {},
      brand_kit_snapshot: {},
      metadata: {},
      created_at: "2026-06-06T00:00:00+00:00"
    }
  })),
  getChatThreadMessages: vi.fn(async () => ({
    success: true,
    messages: [],
    total: 0
  })),
  archiveChatThread: vi.fn(async (threadId: string) => ({
    success: true,
    thread: {
      thread_id: threadId,
      title: "삭제된 작업방",
      status: "archived",
      final_brief: {},
      active_job_id: null,
      has_final_output: false,
      last_message_at: "2026-06-07T00:00:00+00:00",
      archived_at: "2026-06-07T00:00:00+00:00",
      created_at: "2026-06-07T00:00:00+00:00",
      updated_at: "2026-06-07T00:00:00+00:00"
    }
  })),
  updateArchiveItem: vi.fn(async (archiveItemId: string, input: { status: "saved" | "favorite" }) => ({
    item: {
      adId: archiveItemId,
      title: "DB 저장 광고",
      imageUrl: "/api/generated-assets?path=data%2Foutputs%2Fjob_db_1%2Ffinal.png",
      thumbnailUrl: "/api/generated-assets?path=data%2Foutputs%2Fjob_db_1%2Ffinal.png",
      status: input.status,
      adFormat: "1:1",
      platform: "인스타 피드",
      source: "generated",
      metadata: { subtitle: "카페 · 인스타 피드", fileName: "final.png", fileType: "PNG", tags: ["카페", "피드"] }
    }
  })),
  deleteArchiveItem: vi.fn(async (archiveItemId: string) => ({
    item: {
      adId: archiveItemId,
      title: "삭제된 광고",
      status: "saved",
      source: "generated",
      metadata: {}
    }
  }))
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: navigationMock.push,
    back: navigationMock.back,
    replace: navigationMock.replace
  }),
  useSearchParams: () => searchParamsMock.value
}));

async function waitForReferenceTemplatesLoaded() {
  await waitFor(() => expect(screen.getByText("수박주스 블루 여름 피드")).toBeTruthy());
  await waitFor(() => expect(screen.queryByLabelText("샘플 목록 불러오는 중")).toBeNull());
}

async function flushAsyncEffects() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

type ApiClientModule = typeof import("@/lib/api-client");

function mockInitialAutoPilotBrief(api: ApiClientModule) {
  vi.mocked(api.createGenerationJob).mockResolvedValueOnce({
    success: true,
    job: {
      job_id: "job_auto_pilot",
      thread_id: "thread_1",
      status: "done",
      progress: { progress_percent: 100, current_stage: "completed" },
      result_payload: {
        context: {
          businessType: "카페",
          itemOrService: "딸기라떼",
          promotionGoal: "신메뉴 출시"
        },
        brief: {
          purpose: "신메뉴 출시",
          item: "딸기라떼",
          copy: "AI가 고른 딸기라떼 한 잔",
          tone: "브랜드에 맞춘 분위기",
          channel: "인스타 피드 (1:1)",
          imageDirection: "딸기라떼 중심의 깔끔한 광고 배경과 문구 여백을 구성해요.",
          finalImagePath: "data/outputs/job_auto_pilot/final_composite.png"
        },
        copyGenerationMode: "auto_pilot"
      },
      metadata: {},
      created_at: "2026-06-05T00:00:00.000Z",
      updated_at: "2026-06-05T00:00:00.000Z"
    }
  });
}

function mockInitialNoCopyBrief(api: ApiClientModule) {
  vi.mocked(api.createGenerationJob).mockResolvedValueOnce({
    success: true,
    job: {
      job_id: "job_no_copy",
      thread_id: "thread_1",
      status: "done",
      progress: { progress_percent: 100, current_stage: "completed" },
      result_payload: {
        context: {
          businessType: "카페",
          itemOrService: "딸기라떼",
          promotionGoal: "광고 홍보"
        },
        brief: {
          purpose: "광고 홍보",
          item: "딸기라떼",
          copy: "문구 없이 이미지로만",
          tone: "브랜드에 맞춘 분위기",
          channel: "인스타 피드 (1:1)",
          imageDirection: "딸기라떼 중심의 깔끔한 광고 배경과 문구 여백을 구성해요.",
          finalImagePath: "data/outputs/job_no_copy/final_composite.png"
        },
        copyGenerationMode: "no_copy"
      },
      metadata: {},
      created_at: "2026-06-05T00:00:00.000Z",
      updated_at: "2026-06-05T00:00:00.000Z"
    }
  });
}

function findFinalGenerationJobPayload(api: ApiClientModule) {
  return vi.mocked(api.createGenerationJob).mock.calls.find(([payload]) => {
    const metadata = typeof payload.metadata === "object" && payload.metadata
      ? (payload.metadata as Record<string, unknown>)
      : {};
    return metadata.source === "web_generation_flow";
  })?.[0];
}

describe("ChatGenerateClient", () => {
  beforeEach(() => {
    navigationMock.push.mockClear();
    navigationMock.back.mockClear();
    navigationMock.replace.mockClear();
    searchParamsMock.value = new URLSearchParams();
    window.sessionStorage.clear();
    window.localStorage.clear();
  });

  it("restores waiting graph question from a thread snapshot", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.getChatThreadMessages).mockResolvedValueOnce({
      success: true,
      total: 3,
      messages: [
        {
          message_id: "msg_1",
          thread_id: "thread_waiting",
          sequence_no: 1,
          role: "user",
          content: "처음 요청한 광고 내용",
          payload: {},
          created_at: "2026-06-06T00:00:00+00:00"
        },
        {
          message_id: "msg_2",
          thread_id: "thread_waiting",
          sequence_no: 2,
          role: "assistant",
          content: "홍보할 상품이나 서비스는 무엇인가요?",
          payload: {},
          created_at: "2026-06-06T00:01:00+00:00"
        },
        {
          message_id: "msg_3",
          thread_id: "thread_waiting",
          sequence_no: 3,
          role: "user",
          content: null,
          payload: { display_text: "카페" },
          created_at: "2026-06-06T00:02:00+00:00"
        }
      ]
    });
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    searchParamsMock.value = new URLSearchParams("threadId=thread_waiting");
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" />);

    await waitFor(() => expect(screen.getAllByText("홍보할 상품이나 서비스는 무엇인가요?").length).toBeGreaterThan(0));
    expect(screen.getByText("처음 요청한 광고 내용")).toBeTruthy();
    expect(screen.getAllByText("카페").length).toBeGreaterThan(0);
  });

  it("restores nested graph context while showing a waiting job question", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.getChatThreadState).mockResolvedValueOnce({
      success: true,
      snapshot: {
        snapshot_id: "snapshot_reference_waiting",
        thread_id: "thread_reference_waiting",
        job_id: "job_reference_waiting",
        snapshot_version: 1,
        schema_version: 1,
        snapshot_kind: "waiting_user_input",
        state_payload: {
          user_input: "고기집 원육 세팅 피드 스타일로 고기92의 음식점 광고를 만들어줘",
          context: {
            business_type: "restaurant",
            item_or_service: "원육",
            promotion_goal: null
          },
          pending_interrupt: {
            type: "option_question",
            option_question: {
              field: "promotion_goal",
              question: "어떤 목적의 광고를 만들까요?",
              options: [{ id: 1, label: "할인 이벤트", value: "discount_event" }]
            }
          }
        },
        changed_fields: [],
        reference_template_snapshot: {},
        brand_kit_snapshot: {},
        metadata: {},
        created_at: "2026-06-06T00:00:00+00:00"
      }
    });
    vi.mocked(api.getChatThreadMessages).mockResolvedValueOnce({
      success: true,
      total: 1,
      messages: [
        {
          message_id: "msg_reference_waiting",
          thread_id: "thread_reference_waiting",
          sequence_no: 1,
          role: "user",
          content: "고기집 원육 세팅 피드 스타일로 고기92의 음식점 광고를 만들어줘",
          payload: {},
          created_at: "2026-06-06T00:00:00+00:00"
        }
      ]
    });
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    searchParamsMock.value = new URLSearchParams("threadId=thread_reference_waiting");
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" />);

    await waitFor(() => expect(screen.getAllByText("어떤 목적의 광고를 만들까요?").length).toBeGreaterThan(0));
    expect(screen.getByText("음식점/식당")).toBeTruthy();
    expect(screen.getByText("원육")).toBeTruthy();
    expect(screen.getAllByText("확인 필요")).toHaveLength(1);
  });

  it("merges waiting job metadata context when the restored snapshot is empty", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.getGenerationJob).mockResolvedValueOnce({
      success: true,
      job: {
        job_id: "job_reference_waiting",
        thread_id: "thread_reference_waiting",
        status: "waiting_user_input",
        progress: { progress_percent: 50, current_stage: "waiting_user_input" },
        result_payload: null,
        metadata: {
          context: {
            business_type: "restaurant",
            item_or_service: "원육",
            promotion_goal: null
          },
          pending_interrupt: {
            type: "option_question",
            option_question: {
              field: "promotion_goal",
              question: "어떤 목적의 광고를 만들까요?",
              options: [{ id: 1, label: "할인 이벤트", value: "discount_event" }]
            }
          }
        },
        created_at: "2026-06-06T00:00:00+00:00",
        updated_at: "2026-06-06T00:00:00+00:00"
      }
    });
    vi.mocked(api.getChatThreadState).mockResolvedValueOnce({
      success: true,
      snapshot: {
        snapshot_id: "snapshot_reference_waiting_empty_context",
        thread_id: "thread_reference_waiting",
        job_id: "job_reference_waiting",
        snapshot_version: 1,
        schema_version: 1,
        snapshot_kind: "waiting_user_input",
        state_payload: {
          user_input: "고기집 원육 세팅 피드 스타일로 고기92의 음식점 광고를 만들어줘",
          pending_interrupt: {
            type: "option_question",
            option_question: {
              field: "promotion_goal",
              question: "어떤 목적의 광고를 만들까요?",
              options: [{ id: 1, label: "할인 이벤트", value: "discount_event" }]
            }
          }
        },
        changed_fields: [],
        reference_template_snapshot: {},
        brand_kit_snapshot: {},
        metadata: {},
        created_at: "2026-06-06T00:00:00+00:00"
      }
    });
    vi.mocked(api.getChatThreadMessages).mockResolvedValueOnce({
      success: true,
      total: 1,
      messages: [
        {
          message_id: "msg_reference_waiting",
          thread_id: "thread_reference_waiting",
          sequence_no: 1,
          role: "user",
          content: "고기집 원육 세팅 피드 스타일로 고기92의 음식점 광고를 만들어줘",
          payload: {},
          created_at: "2026-06-06T00:00:00+00:00"
        }
      ]
    });
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    searchParamsMock.value = new URLSearchParams("jobId=job_reference_waiting");
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" initialStage="generating" />);

    await waitFor(() => expect(screen.getAllByText("어떤 목적의 광고를 만들까요?").length).toBeGreaterThan(0));
    expect(screen.getByText("음식점/식당")).toBeTruthy();
    expect(screen.getByText("원육")).toBeTruthy();
    expect(screen.getAllByText("확인 필요")).toHaveLength(1);
  });

  it("shows a thread limit modal and routes home", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.createGenerationJob).mockClear();
    vi.mocked(api.createGenerationJob).mockRejectedValueOnce(
      new api.ApiError("작업은 최대 3개까지만 만들 수 있어요. 새 작업을 시작하려면 기존 작업 하나를 삭제해주세요.", {
        errorCode: "thread_limit_reached",
        status: 409
      })
    );
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" />);

    fireEvent.change(screen.getByLabelText("광고 요청 입력"), {
      target: { value: "우리 카페 딸기라떼 신메뉴 광고 만들어줘" }
    });
    fireEvent.click(screen.getByLabelText("요청 보내기"));

    await waitFor(() => expect(screen.getByText(/작업은 최대 3개까지만 만들 수 있어요/)).toBeTruthy());
    expect(screen.queryByText("AI가 이렇게 이해했어요")).toBeNull();
    expect((screen.getByLabelText("광고 요청 입력") as HTMLTextAreaElement).value).toBe("우리 카페 딸기라떼 신메뉴 광고 만들어줘");
    fireEvent.click(screen.getByRole("button", { name: "홈으로 이동" }));

    expect(navigationMock.push).toHaveBeenCalledWith("/");
  });

  it("returns generic initial prompt failures to the start screen with the prompt intact", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.createGenerationJob).mockClear();
    vi.mocked(api.createGenerationJob).mockRejectedValueOnce(new Error("생성 요청에 실패했습니다."));
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" />);

    fireEvent.change(screen.getByLabelText("광고 요청 입력"), {
      target: { value: "우리 카페 딸기라떼 신메뉴 광고 만들어줘" }
    });
    fireEvent.click(screen.getByLabelText("요청 보내기"));

    await waitFor(() => expect(screen.getByText("생성 요청에 실패했습니다.")).toBeTruthy());
    expect(screen.queryByText("AI가 이렇게 이해했어요")).toBeNull();
    expect((screen.getByLabelText("광고 요청 입력") as HTMLTextAreaElement).value).toBe("우리 카페 딸기라떼 신메뉴 광고 만들어줘");
  });

  it("starts reference requests as a fresh chat instead of restoring the previous snapshot", async () => {
    const api = await import("@/lib/api-client");
    const { saveGenerationRequestContext } = await import("@/lib/generation-request-context");
    vi.mocked(api.createGenerationJob).mockClear();
    window.sessionStorage.setItem(
      "easyads_chat_flow_snapshot_v1",
      JSON.stringify({
        prompt: "이전 작업방 요청",
        jobId: "old_job",
        threadId: "old_thread",
        context: {
          businessType: "음식점",
          itemOrService: "삼겹살",
          promotionGoal: "회식 홍보"
        },
        copyCandidates: [{ id: "copy_1", headline: "이전 작업방 문구" }],
        copyCandidateSource: "backend",
        selectedCopyId: "copy_1",
        selectedChannelId: "instagram-feed",
        selectedTone: "강렬한",
        customDirection: "",
        brief: {
          purpose: "회식 홍보",
          item: "삼겹살",
          copy: "이전 작업방 문구",
          tone: "강렬한 분위기",
          channel: "인스타 피드 (1:1)",
          imageDirection: "이전 작업방 이미지 방향",
          finalImagePath: "data/outputs/old_job/final_composite.png"
        },
        imageGenerationEngine: "gpt_image_1",
        sourceImagePath: null,
        referenceImagePath: null
      })
    );
    saveGenerationRequestContext({
      selectedReferenceTemplateId: "ref_cafe_green",
      selectedReferenceTemplateTitle: "초록 카페 레퍼런스",
      draftPrompt: "초록 카페 레퍼런스 스타일로 광고 만들어줘",
      source: "manual"
    });
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" />);

    await waitFor(() => expect(screen.getByText("대화로 찰떡 이미지 만들기")).toBeTruthy());
    expect(screen.queryByText("이전 작업방 문구")).toBeNull();
    expect((screen.getByLabelText("광고 요청 입력") as HTMLTextAreaElement).value).toBe("초록 카페 레퍼런스 스타일로 광고 만들어줘");

    fireEvent.click(screen.getByLabelText("요청 보내기"));

    await waitFor(() =>
      expect(api.createGenerationJob).toHaveBeenCalledWith(
        expect.objectContaining({
          threadId: undefined,
          selectedReferenceTemplateId: "ref_cafe_green"
        })
      )
    );
  });

  it("keeps inferred context visible when a reference request needs one more answer", async () => {
    const api = await import("@/lib/api-client");
    const { saveGenerationRequestContext } = await import("@/lib/generation-request-context");
    vi.mocked(api.createGenerationJob).mockClear();
    saveGenerationRequestContext({
      selectedReferenceTemplateId: "ref_meat_feed",
      selectedReferenceTemplateTitle: "고기집 원육 세일 피드",
      draftPrompt: "고기집 원육 세일 피드 스타일로 음식점 광고를 만들어줘",
      source: "manual"
    });
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" />);

    await waitFor(() => expect(screen.getByText("대화로 찰떡 이미지 만들기")).toBeTruthy());
    fireEvent.click(screen.getByLabelText("요청 보내기"));

    await waitFor(() => expect(screen.getAllByText("홍보할 상품이나 서비스는 무엇인가요?")).toHaveLength(2));
    expect(screen.getByText("음식점/식당")).toBeTruthy();
    expect(screen.getByText("할인 이벤트")).toBeTruthy();
    expect(api.createGenerationJob).toHaveBeenCalledWith(
      expect.objectContaining({
        selectedReferenceTemplateId: "ref_meat_feed"
      })
    );
  });

  it("archives the currently open chat thread from the conversation header", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.archiveChatThread).mockClear();
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    searchParamsMock.value = new URLSearchParams("threadId=thread_waiting");
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" />);

    await waitFor(() => expect(screen.getAllByText("홍보할 상품이나 서비스는 무엇인가요?").length).toBeGreaterThan(0));
    fireEvent.click(screen.getByRole("button", { name: "작업방 삭제" }));
    expect(screen.getByRole("dialog", { name: "이 작업방을 삭제할까요?" })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "삭제" }));

    await waitFor(() => expect(api.archiveChatThread).toHaveBeenCalledWith("thread_waiting"));
    await waitFor(() => expect(navigationMock.push).toHaveBeenCalledWith("/studio"));
  });

  it("walks through the four chat generation steps", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.createChatBrief).mockClear();
    vi.mocked(api.createGenerationJob).mockClear();
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient />);

    expect(screen.getByText("샘플 보고 만들기")).toBeTruthy();
    fireEvent.click(screen.getByText("대화로 시작하기"));
    expect(screen.getByText("대화로 찰떡 이미지 만들기")).toBeTruthy();
    expect(screen.getByLabelText("요청 보내기").hasAttribute("disabled")).toBe(true);
    fireEvent.click(screen.getByText("우리 카페 딸기라떼 신메뉴 광고 만들어줘"));
    fireEvent.click(screen.getByLabelText("요청 보내기"));

    await waitFor(() => expect(screen.getByText("AI가 이렇게 이해했어요")).toBeTruthy());
    expect(screen.getByText("요청 분석")).toBeTruthy();
    expect(screen.getByText(/요청에 대한 분석 결과/)).toBeTruthy();
    await waitFor(() => expect(screen.getByText("딸기라떼")).toBeTruthy());
    await waitFor(() => expect(screen.getByRole("button", { name: "문구 고르기" }).hasAttribute("disabled")).toBe(false));
    fireEvent.click(screen.getByText("상큼한"));
    fireEvent.click(screen.getByText("문구 고르기"));

    expect(screen.getByText("채널과 방향을 골라주세요")).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "추천 문구" })).toBeNull();
    expect(screen.queryByText("자동 추천")).toBeNull();
    fireEvent.click(screen.getByText("인스타 스토리"));
    fireEvent.click(screen.getByText("브리프 확인하기"));

    expect(api.createChatBrief).not.toHaveBeenCalled();
    await waitFor(() => expect(screen.getByText("AI가 브리프를 정리했어요")).toBeTruthy());
    expect(screen.getByText("인스타 스토리 (9:16)")).toBeTruthy();
    expect(screen.getByText("다음 단계에서 선택")).toBeTruthy();

    fireEvent.click(screen.getByText(/이 내용으로 이미지 생성/));
    await waitFor(() =>
      expect(api.createGenerationJob).toHaveBeenCalledWith(
        expect.objectContaining({
          runMode: "graph_job",
          adFormat: "instagram_story",
          copyGenerationMode: "suggest_candidates",
          selectedCopyId: null,
          selectedChannelId: "instagram-story",
          selectedTone: "상큼한",
          customDirection: "",
          userCustomHeadline: undefined,
          userCustomSubcopy: undefined,
          metadata: expect.objectContaining({
            selected_engine: "gpt_image_1",
            requested_engine: "gpt_image_1",
            t2i_engine: "gpt_image_1",
            selected_engine_label: "GPT-image-1",
            selected_copy_id: null,
            legacy_preview_copy_id: "copy_1",
            selected_channel_id: "instagram-story",
            selected_ad_format: "instagram_story",
            selected_tone: "상큼한",
            copy_generation_mode: "suggest_candidates",
            original_copy_generation_mode: "suggest_candidates",
            user_custom_headline: null
          })
        })
      )
    );
    const finalPayload = findFinalGenerationJobPayload(api);
    expect(finalPayload?.userInput).toBe("우리 카페 딸기라떼 신메뉴 광고 만들어줘");
    expect(finalPayload?.userInput).not.toContain("광고 브리프");
    expect(finalPayload?.metadata).toEqual(
      expect.objectContaining({
        final_brief: expect.objectContaining({
          item: "딸기라떼",
          channel: "인스타 스토리 (9:16)"
        })
      })
    );
    await waitFor(() => expect(screen.getByText("광고 이미지 생성이 완료됐어요")).toBeTruthy());
    expect(screen.getByText("GPT-image-1")).toBeTruthy();
    expect(screen.getByText("완성된 이미지는 보관함에서 확인할 수 있어요.")).toBeTruthy();
    expect(screen.queryByText("실제 이미지 파일을 받지 못했어요")).toBeNull();

    fireEvent.click(screen.getByText("참고할 스타일 더 보기"));
    expect(screen.getByText("찰떡 광고 샘플 둘러보기")).toBeTruthy();
    expect(screen.getByText("결과로 돌아가기")).toBeTruthy();
    await waitForReferenceTemplatesLoaded();
  });

  it("waits for a generation job id before navigating to the generating route", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.createGenerationJob).mockClear();
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient />);

    fireEvent.click(screen.getByText("대화로 시작하기"));
    fireEvent.click(screen.getByText("우리 카페 딸기라떼 신메뉴 광고 만들어줘"));
    fireEvent.click(screen.getByLabelText("요청 보내기"));

    await waitFor(() => expect(screen.getByText("AI가 이렇게 이해했어요")).toBeTruthy());
    await waitFor(() => expect(screen.getByRole("button", { name: "문구 고르기" }).hasAttribute("disabled")).toBe(false));
    fireEvent.click(screen.getByText("상큼한"));
    fireEvent.click(screen.getByText("문구 고르기"));
    fireEvent.click(screen.getByText("인스타 스토리"));
    fireEvent.click(screen.getByText("브리프 확인하기"));
    await waitFor(() => expect(screen.getByText("AI가 브리프를 정리했어요")).toBeTruthy());

    fireEvent.click(screen.getByText(/이 내용으로 이미지 생성/));

    await waitFor(() => expect(api.createGenerationJob).toHaveBeenCalled());
    expect(navigationMock.push).not.toHaveBeenCalledWith("/generate/chat/generating");
    await waitFor(() =>
      expect(navigationMock.replace).toHaveBeenCalledWith("/generate/chat/generating?jobId=generation_job_1&threadId=thread_1")
    );
  });

  it("lets users refine the brief before starting image generation", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.createChatBrief).mockClear();
    vi.mocked(api.createChatBrief)
      .mockResolvedValueOnce({
        jobId: "job_1",
        threadId: "thread_1",
        status: "done",
        brief: {
          purpose: "신메뉴 출시",
          item: "딸기라떼",
          copy: "봄을 닮은 한 잔, 딸기라떼 출시",
          tone: "상큼한 분위기",
          channel: "인스타 스토리 (9:16)",
          imageDirection: "상큼한 분위기를 살려 딸기라떼 중심의 깔끔한 광고 배경과 문구 여백을 구성해요.",
          finalImagePath: "data/outputs/job_1/final_composite.png"
        }
      })
      .mockResolvedValueOnce({
        jobId: "job_1",
        threadId: "thread_1",
        status: "done",
        brief: {
          purpose: "신메뉴 출시",
          item: "딸기라떼",
          copy: "봄을 닮은 한 잔, 딸기라떼 출시",
          tone: "상큼한 분위기",
          channel: "인스타 스토리 (9:16)",
          imageDirection: "딸기라떼를 화면 중앙에 더 크게 배치하고 문구 여백을 남겨요.",
          finalImagePath: "data/outputs/job_1/final_composite.png"
        }
      });
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient />);

    fireEvent.click(screen.getByText("대화로 시작하기"));
    fireEvent.click(screen.getByText("우리 카페 딸기라떼 신메뉴 광고 만들어줘"));
    fireEvent.click(screen.getByLabelText("요청 보내기"));

    await waitFor(() => expect(screen.getByRole("button", { name: "문구 고르기" }).hasAttribute("disabled")).toBe(false));
    fireEvent.click(screen.getByText("상큼한"));
    fireEvent.click(screen.getByText("문구 고르기"));
    fireEvent.click(screen.getByText("인스타 스토리"));
    fireEvent.click(screen.getByText("브리프 확인하기"));

    await waitFor(() => expect(screen.getByText("AI가 브리프를 정리했어요")).toBeTruthy());
    fireEvent.change(screen.getByLabelText("브리프 추가 요청 입력"), {
      target: { value: "딸기라떼를 더 크게 보여줘" }
    });
    fireEvent.click(screen.getByLabelText("브리프 추가 요청 보내기"));

    expect(api.createChatBrief).not.toHaveBeenCalled();
    expect(screen.getAllByText("딸기라떼를 더 크게 보여줘").length).toBeGreaterThan(0);
    await waitFor(() => expect(screen.getByText("좋아요. 요청을 반영해서 브리프를 다시 정리했어요.")).toBeTruthy());
    expect(screen.getAllByText("딸기라떼를 더 크게 보여줘").length).toBeGreaterThan(0);
  });

  it("keeps backend analysis pending inside the chat timeline without the review screen", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.createGenerationJob).mockReturnValueOnce(new Promise(() => undefined) as never);
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" />);

    fireEvent.change(screen.getByLabelText("광고 요청 입력"), { target: { value: "우리 카페 딸기라떼 신메뉴 광고 만들어줘" } });
    fireEvent.click(screen.getByLabelText("요청 보내기"));

    expect(screen.getByText("대화로 찰떡 만들기")).toBeTruthy();
    expect(screen.getByText(/요청을 읽고 있어요/)).toBeTruthy();
    expect(screen.queryByText("요청을 살펴보고 있어요")).toBeNull();
    expect(screen.queryByText("진행 중")).toBeNull();
    expect(screen.queryByText(/업종, 상품, 광고 목적을 안전하게 정리/)).toBeNull();
    expect(screen.queryByText("요청 문장 읽는 중")).toBeNull();
    expect(screen.queryByText("딸기라떼")).toBeNull();
    expect(screen.queryByText("카페")).toBeNull();
    expect(screen.queryByText("신메뉴 출시")).toBeNull();
    expect(screen.queryByRole("button", { name: "살펴보는 중..." })).toBeNull();
  });

  it("does not show image generation progress while the initial chat graph job is still analyzing", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.createGenerationJob).mockClear();
    vi.mocked(api.createGenerationJob).mockResolvedValueOnce({
      success: true,
      job: {
        job_id: "job_initial_analyzing",
        thread_id: "thread_initial_analyzing",
        status: "running",
        progress: { progress_percent: 32, current_stage: "brief_interpretation" },
        result_payload: null,
        metadata: {},
        created_at: "2026-06-05T00:00:00.000Z",
        updated_at: "2026-06-05T00:00:00.000Z"
      }
    });
    vi.mocked(api.getGenerationJob).mockReturnValueOnce(new Promise(() => undefined) as never);
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" />);

    fireEvent.change(screen.getByLabelText("광고 요청 입력"), {
      target: { value: "네일샵 여름 이벤트 인스타 스토리 만들어줘" }
    });
    fireEvent.click(screen.getByLabelText("요청 보내기"));

    await waitFor(() => expect(api.getGenerationJob).toHaveBeenCalledWith("job_initial_analyzing"));
    expect(screen.getByText("대화로 찰떡 만들기")).toBeTruthy();
    expect(screen.getByText(/요청을 읽고 있어요/)).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "광고 생성 중" })).toBeNull();
    expect(screen.queryByText("생성 결과를 준비하고 있어요")).toBeNull();
  });

  it("restores a reference request analysis state after the chat page remounts", async () => {
    const api = await import("@/lib/api-client");
    const { saveGenerationRequestContext } = await import("@/lib/generation-request-context");
    vi.mocked(api.createGenerationJob).mockClear();
    vi.mocked(api.getGenerationJob).mockClear();
    vi.mocked(api.createGenerationJob).mockResolvedValueOnce({
      success: true,
      job: {
        job_id: "job_reference_analyzing",
        thread_id: "thread_reference_analyzing",
        status: "running",
        progress: { progress_percent: 28, current_stage: "brief_interpretation" },
        result_payload: null,
        metadata: {},
        created_at: "2026-06-05T00:00:00.000Z",
        updated_at: "2026-06-05T00:00:00.000Z"
      }
    });
    vi.mocked(api.getGenerationJob).mockReturnValue(new Promise(() => undefined) as never);
    saveGenerationRequestContext({
      selectedReferenceTemplateId: "ref_minimal_cafe",
      selectedReferenceTemplateTitle: "미니멀 카페 피드",
      draftPrompt: "미니멀 카페 피드 스타일로 카페24의 카페 광고를 만들어줘",
      source: "manual"
    });
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    const view = render(<ChatGenerateClient initialSurface="chat" />);

    await waitFor(() => expect(screen.getByText("대화로 찰떡 이미지 만들기")).toBeTruthy());
    fireEvent.click(screen.getByLabelText("요청 보내기"));

    await waitFor(() => expect(api.getGenerationJob).toHaveBeenCalledWith("job_reference_analyzing"));
    expect(screen.getByText("대화로 찰떡 만들기")).toBeTruthy();
    expect(screen.getByText(/요청을 읽고 있어요/)).toBeTruthy();

    view.unmount();
    render(<ChatGenerateClient initialSurface="chat" />);

    await waitFor(() => expect(api.getGenerationJob).toHaveBeenCalledTimes(2));
    expect(screen.getByText("대화로 찰떡 만들기")).toBeTruthy();
    expect(screen.getByText("미니멀 카페 피드 스타일로 카페24의 카페 광고를 만들어줘")).toBeTruthy();
    expect(screen.getByText(/요청을 읽고 있어요/)).toBeTruthy();
    expect(screen.queryByText("대화로 찰떡 이미지 만들기")).toBeNull();
    expect(screen.queryByRole("heading", { name: "광고 생성 중" })).toBeNull();
  });

  it("keeps completed queued initial graph jobs inside the chat brief flow", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.createGenerationJob).mockClear();
    vi.mocked(api.createGenerationJob).mockResolvedValueOnce({
      success: true,
      job: {
        job_id: "job_initial_pending",
        thread_id: "thread_initial_pending",
        status: "queued",
        progress: { progress_percent: 8, current_stage: "queued" },
        result_payload: null,
        metadata: {
          selected_engine_label: "FLUX.2 Klein 4B",
          context: {
            business_type: "beauty_nail",
            item_or_service: "네일 서비스",
            promotion_goal: "seasonal_limited"
          },
          final_brief: {
            purpose: "시즌 한정 홍보",
            item: "네일 서비스",
            copy: "여름 네일은 지금이 딱 좋아요",
            tone: "상큼한 분위기",
            channel: "인스타 스토리 (9:16)",
            imageDirection: "여름 네일아트가 잘 보이도록 밝은 배경과 문구 여백을 구성해요."
          }
        },
        created_at: "2026-06-05T00:00:00.000Z",
        updated_at: "2026-06-05T00:00:00.000Z"
      }
    });
    vi.mocked(api.getGenerationJob).mockResolvedValueOnce({
      success: true,
      job: {
        job_id: "job_initial_pending",
        thread_id: "thread_initial_pending",
        status: "done",
        progress: { progress_percent: 100, current_stage: "completed" },
        result_payload: {
          schema_version: "result_artifact_v1",
          job_id: "job_initial_pending",
          preview_image_url: "/api/generated-assets?path=data%2Foutputs%2Fjob_initial_pending%2Ffinal_0.png",
          download_url: "/api/generated-assets?path=data%2Foutputs%2Fjob_initial_pending%2Ffinal_0.png",
          final_image_path: "data/outputs/job_initial_pending/final_0.png",
          engine: "flux2_klein_4b"
        },
        metadata: {
          selected_engine_label: "FLUX.2 Klein 4B",
          context: {
            business_type: "beauty_nail",
            item_or_service: "네일 서비스",
            promotion_goal: "seasonal_limited"
          },
          final_brief: {
            purpose: "시즌 한정 홍보",
            item: "네일 서비스",
            copy: "여름 네일은 지금이 딱 좋아요",
            tone: "상큼한 분위기",
            channel: "인스타 스토리 (9:16)",
            imageDirection: "여름 네일아트가 잘 보이도록 밝은 배경과 문구 여백을 구성해요."
          }
        },
        created_at: "2026-06-05T00:00:00.000Z",
        updated_at: "2026-06-05T00:00:00.000Z"
      }
    });
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" />);

    fireEvent.click(screen.getByText("FLUX.2 Klein 4B"));
    fireEvent.change(screen.getByLabelText("광고 요청 입력"), {
      target: { value: "네일샵 여름 이벤트 인스타 스토리 만들어줘" }
    });
    fireEvent.click(screen.getByLabelText("요청 보내기"));

    await waitFor(() =>
      expect(api.createGenerationJob).toHaveBeenCalledWith(
        expect.objectContaining({
          userInput: expect.stringContaining("네일샵 여름 이벤트 인스타 스토리 만들어줘"),
          runMode: "graph_job",
          metadata: expect.objectContaining({
            source: "web_chat_intake",
            selected_engine: "flux2_klein_4b",
            requested_engine: "flux2_klein_4b",
            t2i_engine: "flux2_klein_4b",
            selected_engine_label: "FLUX.2 Klein 4B"
          })
        })
      )
    );
    await waitFor(() => expect(api.getGenerationJob).toHaveBeenCalledWith("job_initial_pending"));
    await waitFor(() => expect(screen.getByText("AI가 브리프를 정리했어요")).toBeTruthy());
    expect(screen.getByText("광고 브리프 요약")).toBeTruthy();
    expect(screen.getByText("네일 서비스")).toBeTruthy();
    expect(screen.getByText("시즌 한정 홍보")).toBeTruthy();
    expect(screen.queryByText("광고 이미지 생성이 완료됐어요")).toBeNull();
  });

  it("shows context from an initial graph job option question for reference-style requests", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.createGenerationJob).mockClear();
    vi.mocked(api.createGenerationJob).mockResolvedValueOnce({
      success: true,
      job: {
        job_id: "job_reference_question",
        thread_id: "thread_reference_question",
        status: "waiting_user_input",
        progress: { progress_percent: 50, current_stage: "waiting_user_input" },
        result_payload: null,
        metadata: {
          context: {
            business_type: "restaurant",
            item_or_service: "원육"
          },
          pending_interrupt: {
            type: "option_question",
            option_question: {
              field: "promotion_goal",
              question: "어떤 목적의 광고를 만들까요?",
              options: [
                { id: 1, label: "신메뉴/신상품 출시", value: "new_launch" },
                { id: 2, label: "시즌 한정 홍보", value: "seasonal_limited" },
                { id: 3, label: "할인 이벤트", value: "discount_event" }
              ]
            }
          }
        },
        created_at: "2026-06-05T00:00:00.000Z",
        updated_at: "2026-06-05T00:00:00.000Z"
      }
    });
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" />);

    fireEvent.change(screen.getByLabelText("광고 요청 입력"), {
      target: { value: "고기집 원육 세팅 피드 스타일로 고기99의 음식점 광고를 만들어줘" }
    });
    fireEvent.click(screen.getByLabelText("요청 보내기"));

    await waitFor(() => expect(screen.getAllByText("어떤 목적의 광고를 만들까요?").length).toBeGreaterThan(0));
    expect(screen.getByText("음식점/식당")).toBeTruthy();
    expect(screen.getByText("원육")).toBeTruthy();
    expect(screen.getAllByText("확인 필요")).toHaveLength(1);
  });

  it("routes initial copy-candidate interrupts into copy selection instead of an empty question screen", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.createGenerationJob).mockResolvedValueOnce({
      success: true,
      job: {
        job_id: "job_copy_interrupt",
        thread_id: "thread_copy_interrupt",
        status: "waiting_user_input",
        progress: { progress_percent: 50, current_stage: "waiting_user_input" },
        result_payload: null,
        metadata: {
          context: {
            business_type: "beauty_nail",
            item_or_service: "네일 서비스",
            promotion_goal: "seasonal_limited"
          },
          pending_interrupt: {
            type: "copy_candidate_selection",
            candidates: [
              {
                id: "copy_1",
                headline: "여름 네일은 지금이 딱 좋아요",
                subcopy: "시즌 한정 디자인으로 산뜻하게",
                cta: "예약 문의하기"
              }
            ],
            recommended_candidate_id: "copy_1"
          }
        },
        created_at: "2026-06-05T00:00:00.000Z",
        updated_at: "2026-06-05T00:00:00.000Z"
      }
    });
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" />);

    fireEvent.change(screen.getByLabelText("광고 요청 입력"), {
      target: { value: "네일샵 여름 이벤트 인스타 스토리 만들어줘" }
    });
    fireEvent.click(screen.getByLabelText("요청 보내기"));

    // Copy-selection interrupt must stop for an explicit user choice, not auto-pick the
    // recommended candidate and advance to the brief review screen.
    await waitFor(() => expect(screen.getByRole("heading", { name: "사용할 문구를 골라주세요" })).toBeTruthy());
    expect(screen.getByText("여름 네일은 지금이 딱 좋아요")).toBeTruthy();
    expect(screen.queryByText("AI가 이렇게 이해했어요")).toBeNull();
    expect(screen.queryByText("추가 정보가 필요합니다.")).toBeNull();
  });

  it("routes polled initial copy-candidate interrupts into copy selection", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.createGenerationJob).mockResolvedValueOnce({
      success: true,
      job: {
        job_id: "job_initial_copy_poll",
        thread_id: "thread_initial_copy_poll",
        status: "running",
        progress: { progress_percent: 24, current_stage: "brief_interpretation" },
        result_payload: null,
        metadata: {},
        created_at: "2026-06-05T00:00:00.000Z",
        updated_at: "2026-06-05T00:00:00.000Z"
      }
    });
    vi.mocked(api.getGenerationJob).mockResolvedValueOnce({
      success: true,
      job: {
        job_id: "job_initial_copy_poll",
        thread_id: "thread_initial_copy_poll",
        status: "waiting_user_input",
        progress: { progress_percent: 50, current_stage: "copy_selection" },
        result_payload: null,
        metadata: {
          context: {
            business_type: "beauty_nail",
            item_or_service: "네일 서비스",
            promotion_goal: "seasonal_limited"
          },
          pending_interrupt: {
            type: "copy_candidate_selection",
            candidates: [
              {
                id: "copy_1",
                headline: "여름 네일은 지금이 딱 좋아요",
                subcopy: "시즌 한정 디자인으로 산뜻하게",
                cta: "예약 문의하기"
              }
            ],
            recommended_candidate_id: "copy_1"
          }
        },
        created_at: "2026-06-05T00:00:00.000Z",
        updated_at: "2026-06-05T00:00:00.000Z"
      }
    });
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" />);

    fireEvent.change(screen.getByLabelText("광고 요청 입력"), {
      target: { value: "네일샵 여름 이벤트 인스타 스토리 만들어줘" }
    });
    fireEvent.click(screen.getByLabelText("요청 보내기"));

    // Polled copy-selection interrupt routes to the same selection screen as the
    // synchronous path — no auto-pick, no auto-advance to the brief review.
    await waitFor(() => expect(screen.getByRole("heading", { name: "사용할 문구를 골라주세요" })).toBeTruthy());
    expect(screen.getByText("여름 네일은 지금이 딱 좋아요")).toBeTruthy();
    expect(screen.queryByText("AI가 이렇게 이해했어요")).toBeNull();
  });

  it("renders a no-copy brief without surfacing copy selection", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.createGenerationJob).mockClear();
    mockInitialNoCopyBrief(api);
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" />);

    fireEvent.change(screen.getByLabelText("광고 요청 입력"), {
      target: { value: "우리 카페 딸기라떼 이미지만 광고 만들어줘" }
    });
    fireEvent.click(screen.getByLabelText("요청 보내기"));

    // B2: copy mode is no longer chosen up front, so it is never sent at job creation.
    await waitFor(() => expect(api.createGenerationJob).toHaveBeenCalled());
    const [createPayload] = vi.mocked(api.createGenerationJob).mock.calls[0];
    expect(createPayload.copyGenerationMode).toBeUndefined();

    await waitFor(() => expect(screen.getByText("AI가 브리프를 정리했어요")).toBeTruthy());
    expect(screen.getByText("문구 없이 이미지로만")).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "추천 문구" })).toBeNull();
  });

  it("renders an auto-pilot brief without surfacing copy selection", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.createGenerationJob).mockClear();
    mockInitialAutoPilotBrief(api);
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" />);

    fireEvent.change(screen.getByLabelText("광고 요청 입력"), {
      target: { value: "우리 카페 딸기라떼 신메뉴 광고 만들어줘" }
    });
    fireEvent.click(screen.getByLabelText("요청 보내기"));

    await waitFor(() => expect(api.createGenerationJob).toHaveBeenCalled());
    const [createPayload] = vi.mocked(api.createGenerationJob).mock.calls[0];
    expect(createPayload.copyGenerationMode).toBeUndefined();

    await waitFor(() => expect(screen.getByText("AI가 브리프를 정리했어요")).toBeTruthy());
    expect(screen.getByText("AI가 고른 딸기라떼 한 잔")).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "추천 문구" })).toBeNull();
  });

  it("creates the final generation job with the selected FLUX engine", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.createGenerationJob).mockClear();
    mockInitialAutoPilotBrief(api);
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" />);

    fireEvent.change(screen.getByLabelText("광고 요청 입력"), {
      target: { value: "우리 카페 딸기라떼 신메뉴 광고 만들어줘" }
    });
    fireEvent.click(screen.getByText("FLUX.2 Klein 4B"));
    fireEvent.click(screen.getByLabelText("요청 보내기"));

    await waitFor(() => expect(screen.getByText("AI가 브리프를 정리했어요")).toBeTruthy());
    fireEvent.click(screen.getByText(/이 내용으로 이미지 생성/));

    await waitFor(() =>
      expect(api.createGenerationJob).toHaveBeenCalledWith(
        expect.objectContaining({
          runMode: "graph_job",
          metadata: expect.objectContaining({
            selected_engine: "flux2_klein_4b",
            requested_engine: "flux2_klein_4b",
            t2i_engine: "flux2_klein_4b",
            selected_engine_label: "FLUX.2 Klein 4B"
          })
        })
      )
    );
    await waitFor(() => expect(screen.getByText("FLUX.2 Klein 4B")).toBeTruthy());
  });

  it("passes uploaded referenceImagePath to chat start and the final generation job", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.uploadReferenceAsset).mockClear();
    vi.mocked(api.createGenerationJob).mockClear();
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" />);

    const file = new File([new Uint8Array([1, 2, 3])], "reference.png", { type: "image/png" });
    fireEvent.change(screen.getByLabelText("레퍼런스 이미지 첨부"), { target: { files: [file] } });
    fireEvent.change(screen.getByLabelText("광고 요청 입력"), {
      target: { value: "이 분위기로 딸기라떼 광고 만들어줘" }
    });
    fireEvent.click(screen.getByLabelText("요청 보내기"));

    await waitFor(() => expect(api.uploadReferenceAsset).toHaveBeenCalledWith(file));
    await waitFor(() =>
      expect(api.createGenerationJob).toHaveBeenCalledWith(
        expect.objectContaining({
          userInput: expect.stringContaining("이 분위기로 딸기라떼 광고 만들어줘"),
          referenceImagePath: "data/uploads/reference_1.png"
        })
      )
    );

    await waitFor(() => expect(screen.getByText("AI가 이렇게 이해했어요")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "문구 고르기" }));
    fireEvent.click(screen.getByRole("button", { name: "브리프 확인하기" }));
    await waitFor(() => expect(screen.getByText("AI가 브리프를 정리했어요")).toBeTruthy());

    fireEvent.click(screen.getByText(/이 내용으로 이미지 생성/));

    await waitFor(() =>
      expect(api.createGenerationJob).toHaveBeenCalledWith(
        expect.objectContaining({
          referenceImagePath: "data/uploads/reference_1.png"
        })
      )
    );
  });

  it("answers a pending LangGraph question during final generation", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.createGenerationJob).mockClear();
    vi.mocked(api.answerGenerationJob).mockClear();
    mockInitialAutoPilotBrief(api);
    vi.mocked(api.createGenerationJob).mockResolvedValueOnce({
      success: true,
      job: {
        job_id: "generation_job_waiting",
        thread_id: "thread_generation_waiting",
        status: "waiting_user_input",
        progress: {
          progress_percent: 44,
          current_stage: "context_collection"
        },
        metadata: {
          pending_interrupt: {
            type: "option_question",
            option_question: {
              field: "business_type",
              question: "어떤 업종인가요?",
              options: [
                { id: 1, label: "카페", value: "cafe" },
                { id: 2, label: "음식점", value: "restaurant" }
              ]
            }
          }
        },
        created_at: "2026-06-05T00:00:00.000Z",
        updated_at: "2026-06-05T00:00:00.000Z"
      }
    });
    vi.mocked(api.answerGenerationJob).mockResolvedValueOnce({
      success: true,
      job: {
        job_id: "generation_job_waiting",
        thread_id: "thread_generation_waiting",
        status: "done",
        progress: {
          progress_percent: 100,
          current_stage: "completed"
        },
        result_payload: {
          schema_version: "result_artifact_v1",
          job_id: "generation_job_waiting",
          preview_image_url: "/api/generated-assets?path=data%2Foutputs%2Fgeneration_job_waiting%2Ffinal_0.png",
          download_url: "/api/generated-assets?path=data%2Foutputs%2Fgeneration_job_waiting%2Ffinal_0.png",
          final_image_path: "data/outputs/generation_job_waiting/final_0.png",
          engine: "gpt_image_1"
        },
        metadata: {
          selected_engine_label: "GPT-image-1"
        },
        created_at: "2026-06-05T00:00:00.000Z",
        updated_at: "2026-06-05T00:00:00.000Z"
      }
    });
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" />);

    fireEvent.change(screen.getByLabelText("광고 요청 입력"), {
      target: { value: "우리 카페 딸기라떼 신메뉴 광고 만들어줘" }
    });
    fireEvent.click(screen.getByLabelText("요청 보내기"));

    await waitFor(() => expect(screen.getByText("AI가 브리프를 정리했어요")).toBeTruthy());
    fireEvent.click(screen.getByText(/이 내용으로 이미지 생성/));

    await waitFor(() => expect(screen.getByRole("heading", { name: "어떤 업종인가요?" })).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "카페" }));
    fireEvent.click(await screen.findByRole("button", { name: "선택 완료" }));

    await waitFor(() =>
      expect(api.answerGenerationJob).toHaveBeenCalledWith("generation_job_waiting", {
        field: "business_type",
        value: "cafe",
        displayText: "카페"
      })
    );
    await waitFor(() => expect(screen.getByText("광고 이미지 생성이 완료됐어요")).toBeTruthy());
  });

  it("does not push a jobId-less generating route during final generation (no failure flash)", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.createGenerationJob).mockClear();
    mockInitialAutoPilotBrief(api);
    vi.mocked(api.createGenerationJob).mockResolvedValueOnce({
      success: true,
      job: {
        job_id: "generation_job_final",
        thread_id: "thread_generation_final",
        status: "done",
        progress: {
          progress_percent: 100,
          current_stage: "completed"
        },
        result_payload: {
          schema_version: "result_artifact_v1",
          job_id: "generation_job_final",
          preview_image_url: "/api/generated-assets?path=data%2Foutputs%2Fgeneration_job_final%2Ffinal_0.png",
          download_url: "/api/generated-assets?path=data%2Foutputs%2Fgeneration_job_final%2Ffinal_0.png",
          final_image_path: "data/outputs/generation_job_final/final_0.png",
          engine: "gpt_image_1"
        },
        metadata: {
          selected_engine_label: "GPT-image-1"
        },
        created_at: "2026-06-05T00:00:00.000Z",
        updated_at: "2026-06-05T00:00:00.000Z"
      }
    });
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" />);

    fireEvent.change(screen.getByLabelText("광고 요청 입력"), {
      target: { value: "우리 카페 딸기라떼 신메뉴 광고 만들어줘" }
    });
    fireEvent.click(screen.getByLabelText("요청 보내기"));

    await waitFor(() => expect(screen.getByText("AI가 브리프를 정리했어요")).toBeTruthy());
    navigationMock.push.mockClear();
    navigationMock.replace.mockClear();
    fireEvent.click(screen.getByText(/이 내용으로 이미지 생성/));

    await waitFor(() => expect(screen.getByText("광고 이미지 생성이 완료됐어요")).toBeTruthy());

    // 생성 잡 생성 전에 jobId 없는 `/generate/chat/generating`로 push하면 복원 useEffect가
    // jobId 부재 상태로 재실행돼 생성실패 화면이 잠깐 노출됨. push로는 절대 가면 안 되고
    // jobId가 붙은 href로 replace만 일어나야 함.
    expect(navigationMock.push).not.toHaveBeenCalledWith("/generate/chat/generating");
    const replacedWithJob = navigationMock.replace.mock.calls.some(
      ([href]) => typeof href === "string" && href.includes("/generate/chat/generating") && href.includes("jobId=generation_job_final")
    );
    expect(replacedWithJob).toBe(true);
  });

  it("auto-submits copy_generation_mode custom_input without a 선택 완료 click", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.createGenerationJob).mockClear();
    vi.mocked(api.answerGenerationJob).mockClear();
    mockInitialAutoPilotBrief(api);
    vi.mocked(api.createGenerationJob).mockResolvedValueOnce({
      success: true,
      job: {
        job_id: "generation_job_copy_mode",
        thread_id: "thread_generation_copy_mode",
        status: "waiting_user_input",
        progress: {
          progress_percent: 46,
          current_stage: "context_collection"
        },
        metadata: {
          pending_interrupt: {
            type: "option_question",
            option_question: {
              field: "copy_generation_mode",
              question: "문구는 어떻게 만들까요?",
              options: [
                { id: 1, label: "AI 추천 문구 보기", value: "suggest_candidates" },
                { id: 2, label: "직접 입력할게요", value: "custom_input" }
              ]
            }
          }
        },
        created_at: "2026-06-05T00:00:00.000Z",
        updated_at: "2026-06-05T00:00:00.000Z"
      }
    });
    vi.mocked(api.answerGenerationJob).mockResolvedValueOnce({
      success: true,
      job: {
        job_id: "generation_job_copy_mode",
        thread_id: "thread_generation_copy_mode",
        status: "waiting_user_input",
        progress: {
          progress_percent: 52,
          current_stage: "custom_copy_input"
        },
        metadata: {
          pending_interrupt: {
            type: "custom_copy_input",
            fields: [
              {
                field: "user_custom_headline",
                placeholder: "메인 문구를 입력해주세요",
                required: true,
                max_recommended_chars: 15
              },
              {
                field: "user_custom_subcopy",
                placeholder: "보조 문구를 입력해주세요",
                required: false
              }
            ]
          }
        },
        created_at: "2026-06-05T00:00:00.000Z",
        updated_at: "2026-06-05T00:00:00.000Z"
      }
    });
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" />);

    fireEvent.change(screen.getByLabelText("광고 요청 입력"), {
      target: { value: "우리 카페 딸기라떼 신메뉴 광고 만들어줘" }
    });
    fireEvent.click(screen.getByLabelText("요청 보내기"));

    await waitFor(() => expect(screen.getByText("AI가 브리프를 정리했어요")).toBeTruthy());
    fireEvent.click(screen.getByText(/이 내용으로 이미지 생성/));

    await waitFor(() => expect(screen.getByRole("heading", { name: "문구는 어떻게 만들까요?" })).toBeTruthy());
    const directInputButton = screen.getByRole("button", { name: "직접 입력할게요" });
    expect(directInputButton.parentElement?.className).toContain("copyModeGrid");
    // 직접 입력 칩 클릭만으로 즉시 제출 — 별도 "선택 완료" 버튼이 없어야 함
    fireEvent.click(directInputButton);
    expect(screen.queryByRole("button", { name: "선택 완료" })).toBeNull();

    await waitFor(() =>
      expect(api.answerGenerationJob).toHaveBeenCalledWith("generation_job_copy_mode", {
        field: "copy_generation_mode",
        value: "custom_input",
        displayText: "직접 입력할게요"
      })
    );
    expect(api.answerGenerationJob).toHaveBeenCalledTimes(1);
    // 백엔드 custom_copy_input interrupt 폼으로 진입
    await waitFor(() => expect(screen.getByRole("heading", { name: "광고 문구를 입력해주세요" })).toBeTruthy());
  });

  it("resumes final generation with a selected copy candidate interrupt", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.startChatGeneration).mockClear();
    vi.mocked(api.createGenerationJob).mockClear();
    vi.mocked(api.answerGenerationJob).mockClear();
    mockInitialAutoPilotBrief(api);
    vi.mocked(api.createGenerationJob).mockResolvedValueOnce({
      success: true,
      job: {
        job_id: "generation_job_copy_waiting",
        thread_id: "thread_generation_copy_waiting",
        status: "waiting_user_input",
        progress: {
          progress_percent: 48,
          current_stage: "copy_selection"
        },
        metadata: {
          pending_interrupt: {
            type: "copy_candidate_selection",
            candidates: [
              { id: "copy_1", headline: "오늘 저녁 딸기라떼 한 잔" },
              { id: "copy_2", headline: "오늘만 더 달콤한 신메뉴" }
            ],
            recommended_candidate_id: "copy_1"
          }
        },
        created_at: "2026-06-05T00:00:00.000Z",
        updated_at: "2026-06-05T00:00:00.000Z"
      }
    });
    vi.mocked(api.answerGenerationJob).mockResolvedValueOnce({
      success: true,
      job: {
        job_id: "generation_job_copy_waiting",
        thread_id: "thread_generation_copy_waiting",
        status: "done",
        progress: {
          progress_percent: 100,
          current_stage: "completed"
        },
        result_payload: {
          schema_version: "result_artifact_v1",
          job_id: "generation_job_copy_waiting",
          preview_image_url: "/api/generated-assets?path=data%2Foutputs%2Fgeneration_job_copy_waiting%2Ffinal_0.png",
          download_url: "/api/generated-assets?path=data%2Foutputs%2Fgeneration_job_copy_waiting%2Ffinal_0.png",
          final_image_path: "data/outputs/generation_job_copy_waiting/final_0.png",
          engine: "gpt_image_1"
        },
        created_at: "2026-06-05T00:00:00.000Z",
        updated_at: "2026-06-05T00:00:00.000Z"
      }
    });
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" />);

    fireEvent.change(screen.getByLabelText("광고 요청 입력"), {
      target: { value: "우리 카페 딸기라떼 신메뉴 광고 만들어줘" }
    });
    fireEvent.click(screen.getByLabelText("요청 보내기"));

    await waitFor(() => expect(screen.getByText("AI가 브리프를 정리했어요")).toBeTruthy());
    fireEvent.click(screen.getByText(/이 내용으로 이미지 생성/));

    await waitFor(() => expect(screen.getByRole("heading", { name: "사용할 문구를 골라주세요" })).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "오늘만 더 달콤한 신메뉴 선택" }));

    await waitFor(() =>
      expect(api.answerGenerationJob).toHaveBeenCalledWith("generation_job_copy_waiting", {
        selectedCopyId: "copy_2",
        displayText: "오늘만 더 달콤한 신메뉴",
        payload: {
          selected_channel_id: "instagram-feed",
          selected_ad_format: "instagram_feed",
          selected_tone: "감성적인",
          custom_direction: undefined
        }
      })
    );
    await waitFor(() => expect(screen.getByText("광고 이미지 생성이 완료됐어요")).toBeTruthy());
  });

  it("resumes final generation with custom copy input interrupt", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.startChatGeneration).mockClear();
    vi.mocked(api.createGenerationJob).mockClear();
    vi.mocked(api.answerGenerationJob).mockClear();
    mockInitialAutoPilotBrief(api);
    vi.mocked(api.createGenerationJob).mockResolvedValueOnce({
      success: true,
      job: {
        job_id: "generation_job_custom_waiting",
        thread_id: "thread_generation_custom_waiting",
        status: "waiting_user_input",
        progress: {
          progress_percent: 52,
          current_stage: "custom_copy_input"
        },
        metadata: {
          pending_interrupt: {
            type: "custom_copy_input",
            fields: [
              {
                field: "user_custom_headline",
                placeholder: "메인 문구를 입력해주세요",
                required: true,
                max_recommended_chars: 15
              },
              {
                field: "user_custom_subcopy",
                placeholder: "보조 문구를 입력해주세요",
                required: false
              }
            ]
          }
        },
        created_at: "2026-06-05T00:00:00.000Z",
        updated_at: "2026-06-05T00:00:00.000Z"
      }
    });
    vi.mocked(api.answerGenerationJob).mockResolvedValueOnce({
      success: true,
      job: {
        job_id: "generation_job_custom_waiting",
        thread_id: "thread_generation_custom_waiting",
        status: "done",
        progress: {
          progress_percent: 100,
          current_stage: "completed"
        },
        result_payload: {
          schema_version: "result_artifact_v1",
          job_id: "generation_job_custom_waiting",
          preview_image_url: "/api/generated-assets?path=data%2Foutputs%2Fgeneration_job_custom_waiting%2Ffinal_0.png",
          download_url: "/api/generated-assets?path=data%2Foutputs%2Fgeneration_job_custom_waiting%2Ffinal_0.png",
          final_image_path: "data/outputs/generation_job_custom_waiting/final_0.png",
          engine: "gpt_image_1"
        },
        created_at: "2026-06-05T00:00:00.000Z",
        updated_at: "2026-06-05T00:00:00.000Z"
      }
    });
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" />);

    fireEvent.change(screen.getByLabelText("광고 요청 입력"), {
      target: { value: "우리 카페 딸기라떼 신메뉴 광고 만들어줘" }
    });
    fireEvent.click(screen.getByLabelText("요청 보내기"));

    await waitFor(() => expect(screen.getByText("AI가 브리프를 정리했어요")).toBeTruthy());
    fireEvent.click(screen.getByText(/이 내용으로 이미지 생성/));

    await waitFor(() => expect(screen.getByRole("heading", { name: "광고 문구를 입력해주세요" })).toBeTruthy());
    fireEvent.change(screen.getByLabelText("생성 재개 메인 문구 입력"), {
      target: { value: "오늘만 딸기라떼 반값" }
    });
    fireEvent.change(screen.getByLabelText("생성 재개 보조 문구 입력"), {
      target: { value: "오후 2시부터 5시까지" }
    });
    fireEvent.click(screen.getByRole("button", { name: "문구로 생성 이어가기" }));

    await waitFor(() =>
      expect(api.answerGenerationJob).toHaveBeenCalledWith("generation_job_custom_waiting", {
        displayText: "오늘만 딸기라떼 반값 / 오후 2시부터 5시까지",
        userCustomHeadline: "오늘만 딸기라떼 반값",
        userCustomSubcopy: "오후 2시부터 5시까지"
      })
    );
    await waitFor(() => expect(screen.getByText("광고 이미지 생성이 완료됐어요")).toBeTruthy());
  });

  it("sends compliance cancel decisions to the waiting generation job", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.startChatGeneration).mockClear();
    vi.mocked(api.createGenerationJob).mockClear();
    vi.mocked(api.answerGenerationJob).mockClear();
    mockInitialAutoPilotBrief(api);
    vi.mocked(api.createGenerationJob).mockResolvedValueOnce({
      success: true,
      job: {
        job_id: "generation_job_compliance_waiting",
        thread_id: "thread_generation_compliance_waiting",
        status: "waiting_user_input",
        progress: {
          progress_percent: 55,
          current_stage: "copy_compliance_review"
        },
        metadata: {
          pending_interrupt: {
            type: "copy_compliance_review",
            status: "blocked",
            summary: "광고 규제 위험 표현 1개가 발견되었습니다.",
            findings: [
              {
                finding_id: "finding_1",
                field: "headline",
                matched_text: "여드름 치료",
                severity: "block",
                reason: "화장품의 의약품 오인 표현"
              }
            ],
            actions: [
              { id: "use_suggestion", label: "안전한 문구로 수정", available: true },
              { id: "cancel", label: "생성 취소", available: true }
            ]
          }
        },
        created_at: "2026-06-05T00:00:00.000Z",
        updated_at: "2026-06-05T00:00:00.000Z"
      }
    });
    vi.mocked(api.answerGenerationJob).mockResolvedValueOnce({
      success: true,
      job: {
        job_id: "generation_job_compliance_waiting",
        thread_id: "thread_generation_compliance_waiting",
        status: "failed",
        progress: {
          progress_percent: 55,
          current_stage: "failed"
        },
        error: {
          error_code: "generation_job_cancelled_by_user",
          message: "Generation cancelled by user."
        },
        metadata: {},
        created_at: "2026-06-05T00:00:00.000Z",
        updated_at: "2026-06-05T00:00:00.000Z"
      }
    });
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" />);

    fireEvent.change(screen.getByLabelText("광고 요청 입력"), {
      target: { value: "스킨케어 광고 만들어줘" }
    });
    fireEvent.click(screen.getByLabelText("요청 보내기"));

    await waitFor(() => expect(screen.getByText("AI가 브리프를 정리했어요")).toBeTruthy());
    fireEvent.click(screen.getByText(/이 내용으로 이미지 생성/));

    await waitFor(() => expect(screen.getByRole("heading", { name: "광고 규제 검토 결과" })).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "생성 취소" }));

    await waitFor(() =>
      expect(api.answerGenerationJob).toHaveBeenCalledWith("generation_job_compliance_waiting", {
        action: "cancel",
        displayText: "생성 취소"
      })
    );
  });

  it("shows validation feedback from the final generation result", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.startChatGeneration).mockClear();
    vi.mocked(api.createGenerationJob).mockClear();
    mockInitialAutoPilotBrief(api);
    vi.mocked(api.createGenerationJob).mockResolvedValueOnce({
      success: true,
      job: {
        job_id: "generation_job_validation",
        thread_id: "thread_generation_validation",
        status: "done",
        progress: {
          progress_percent: 100,
          current_stage: "completed"
        },
        result_payload: {
          schema_version: "result_artifact_v1",
          job_id: "generation_job_validation",
          preview_image_url: "/api/generated-assets?path=data%2Foutputs%2Fgeneration_job_validation%2Ffinal_0.png",
          download_url: "/api/generated-assets?path=data%2Foutputs%2Fgeneration_job_validation%2Ffinal_0.png",
          final_image_path: "data/outputs/generation_job_validation/final_0.png",
          engine: "gpt_image_1",
          validation_summary: {
            background: { overall_pass: true },
            safe_area: { overall_pass: true, warnings: ["near_edge"] },
            readability: { overall_pass: false },
            final: { overall_pass: true }
          }
        },
        metadata: {
          selected_engine_label: "GPT-image-1"
        },
        created_at: "2026-06-05T00:00:00.000Z",
        updated_at: "2026-06-05T00:00:00.000Z"
      }
    });
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" />);

    fireEvent.change(screen.getByLabelText("광고 요청 입력"), {
      target: { value: "우리 카페 딸기라떼 신메뉴 광고 만들어줘" }
    });
    fireEvent.click(screen.getByLabelText("요청 보내기"));

    await waitFor(() => expect(screen.getByText("AI가 브리프를 정리했어요")).toBeTruthy());
    fireEvent.click(screen.getByText(/이 내용으로 이미지 생성/));

    await waitFor(() => expect(screen.getByRole("heading", { name: "생성 결과 검수" })).toBeTruthy());
    expect(screen.getByText("이미지 배경이 광고로 쓰기 좋게 준비됐어요.")).toBeTruthy();
    expect(screen.getByText("문구가 들어갈 위치를 한 번 더 확인해보세요.")).toBeTruthy();
    expect(screen.getByText("문구 가독성 개선이 필요해요.")).toBeTruthy();
    expect(screen.queryByText("safe_area_gate")).toBeNull();
  });

  it("does not pick copy mode up front (B2: asked later in the HITL)", async () => {
    // B2: the "문구 포함 여부" chips were removed from the first chat screen so copy
    // mode is asked as the last HITL question after the LLM has the full context.
    // The intake screen must therefore no longer collect or send copyGenerationMode.
    const api = await import("@/lib/api-client");
    vi.mocked(api.startChatGeneration).mockClear();
    vi.mocked(api.createGenerationJob).mockClear();
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" />);

    expect(screen.queryByText("문구 포함 여부")).toBeNull();
    expect(screen.queryByText("직접 문구")).toBeNull();
    expect(screen.queryByText("AI 자동 완성")).toBeNull();

    fireEvent.change(screen.getByLabelText("광고 요청 입력"), {
      target: { value: "우리 카페 딸기라떼 신메뉴 광고 만들어줘" }
    });
    fireEvent.click(screen.getByLabelText("요청 보내기"));

    await waitFor(() => expect(api.createGenerationJob).toHaveBeenCalled());
    const [createPayload] = vi.mocked(api.createGenerationJob).mock.calls[0];
    expect(createPayload.copyGenerationMode).toBeUndefined();
    expect(createPayload.userCustomHeadline).toBeUndefined();
    expect(createPayload.userCustomSubcopy).toBeUndefined();
  });

  it("asks a LangGraph option question when the first prompt lacks context", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.answerGenerationJob).mockResolvedValueOnce({
      success: true,
      job: {
        job_id: "job_question",
        thread_id: "thread_question",
        status: "done",
        progress: { progress_percent: 100, current_stage: "completed" },
        result_payload: {
          type: "copy_candidates",
          context: {
            businessType: "카페",
            itemOrService: "대표 메뉴",
            promotionGoal: "광고 홍보"
          },
          copyCandidates: [{ id: "copy_1", headline: "대표 메뉴를 더 맛있게 알리기" }],
          recommendedCopyId: "copy_1",
          copyCandidateOrigin: "rule_based",
          copyGenerationMode: "suggest_candidates"
        },
        metadata: {},
        created_at: "2026-06-05T00:00:00.000Z",
        updated_at: "2026-06-05T00:00:00.000Z"
      }
    });
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" />);

    fireEvent.change(screen.getByLabelText("광고 요청 입력"), { target: { value: "광고 만들어줘" } });
    fireEvent.click(screen.getByLabelText("요청 보내기"));

    await waitFor(() => expect(screen.getByRole("heading", { name: "어떤 업종의 광고인가요?" })).toBeTruthy());
    expect(screen.getByText("카페/디저트")).toBeTruthy();

    fireEvent.click(screen.getByText("카페/디저트"));
    fireEvent.click(await screen.findByRole("button", { name: "선택 완료" }));

    await waitFor(() => expect(screen.getByText("AI가 이렇게 이해했어요")).toBeTruthy());
    expect(screen.getByText("요청 분석")).toBeTruthy();
    expect(screen.getByText("대표 메뉴")).toBeTruthy();
    expect(api.answerGenerationJob).toHaveBeenCalledWith(
      "job_question",
      expect.objectContaining({
        field: "business_type",
        value: "cafe",
        displayText: "카페/디저트"
      })
    );
  });

  it("locks option answers while a LangGraph answer request is pending", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.answerGenerationJob).mockClear();
    vi.mocked(api.answerGenerationJob).mockReturnValueOnce(new Promise(() => undefined) as never);
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" />);

    fireEvent.change(screen.getByLabelText("광고 요청 입력"), { target: { value: "광고 만들어줘" } });
    fireEvent.click(screen.getByLabelText("요청 보내기"));

    const cafeButton = await screen.findByRole("button", { name: "카페/디저트" });
    fireEvent.click(cafeButton);
    const confirmButton = await screen.findByRole("button", { name: "선택 완료" });
    fireEvent.click(confirmButton);

    await waitFor(() => expect(cafeButton.hasAttribute("disabled")).toBe(true));
    fireEvent.click(cafeButton);

    expect(api.answerGenerationJob).toHaveBeenCalledTimes(1);
    expect(confirmButton.hasAttribute("disabled")).toBe(true);
  });

  it("continues to the pending-copy brief when early backend candidates are missing", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" />);

    fireEvent.change(screen.getByLabelText("광고 요청 입력"), { target: { value: "후보 없는 광고" } });
    fireEvent.click(screen.getByLabelText("요청 보내기"));

    await waitFor(() => expect(screen.getByText("대표 메뉴")).toBeTruthy());
    await waitFor(() => expect(screen.getByRole("button", { name: "문구 고르기" }).hasAttribute("disabled")).toBe(false));
    fireEvent.click(screen.getByText("문구 고르기"));

    expect(screen.getByText("채널과 방향을 골라주세요")).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "추천 문구" })).toBeNull();
    expect(screen.queryByText("문구 후보가 아직 없어요")).toBeNull();
    expect(screen.getByRole("button", { name: "브리프 확인하기" }).hasAttribute("disabled")).toBe(false);
  });

  it("keeps similar style browsing open after generation completes", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.createGenerationJob).mockClear();
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient />);

    fireEvent.click(screen.getByText("대화로 시작하기"));
    fireEvent.click(screen.getByText("우리 카페 딸기라떼 신메뉴 광고 만들어줘"));
    fireEvent.click(screen.getByLabelText("요청 보내기"));
    await waitFor(() => expect(screen.getByText("딸기라떼")).toBeTruthy());
    await waitFor(() => expect(screen.getByRole("button", { name: "문구 고르기" }).hasAttribute("disabled")).toBe(false));
    fireEvent.click(screen.getByText("문구 고르기"));
    expect(screen.getByText("채널과 방향을 골라주세요")).toBeTruthy();
    fireEvent.click(screen.getByText("브리프 확인하기"));
    await waitFor(() => expect(screen.getByText("AI가 브리프를 정리했어요")).toBeTruthy());

    fireEvent.click(screen.getByText(/이 내용으로 이미지 생성/));
    await waitFor(() => expect(api.createGenerationJob).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByText("광고 이미지 생성이 완료됐어요")).toBeTruthy());

    fireEvent.click(screen.getByText("참고할 스타일 더 보기"));

    expect(screen.getByText("찰떡 광고 샘플 둘러보기")).toBeTruthy();
    expect(screen.getByText("결과로 돌아가기")).toBeTruthy();
    expect(screen.queryByText("이미지 생성이 진행 중이거나 표시할 수 없어요")).toBeNull();
    await waitForReferenceTemplatesLoaded();
  });

  it("opens the reference gallery from the home dashboard", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.listReferenceTemplates).mockClear();
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient />);

    fireEvent.click(screen.getByText("샘플 보고 만들기"));
    expect(screen.getByText("SAMPLE GALLERY")).toBeTruthy();
    expect(screen.getByText("찰떡 광고 샘플 둘러보기")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "알림" }));
    expect(navigationMock.push).toHaveBeenCalledWith("/notifications");

    fireEvent.click(screen.getByRole("button", { name: "음식" }));
    await waitFor(() =>
      expect(vi.mocked(api.listReferenceTemplates).mock.calls.some(([params]) => params?.category === "food")).toBe(true)
    );

    fireEvent.click(screen.getByLabelText("홈으로"));
    expect(screen.getByText("샘플 보고 만들기")).toBeTruthy();
  });

  it("opens a selected reference template detail from the gallery", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.createGenerationJob).mockClear();
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="reference" />);

    await waitFor(() => expect(screen.getByText("수박주스 블루 여름 피드")).toBeTruthy());
    expect(screen.queryByRole("button", { name: "수박주스 블루 여름 피드 스타일로 시작" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "수박주스 블루 여름 피드 상세 보기" }));

    expect(navigationMock.push).toHaveBeenCalledWith("/reference/temp_watermelon_juice_feed");
    expect(api.createGenerationJob).not.toHaveBeenCalled();
  });

  it("shows cached reference templates immediately while refreshing the gallery", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.listReferenceTemplates).mockClear();
    vi.mocked(api.listReferenceTemplates).mockReturnValueOnce(new Promise(() => undefined));
    window.localStorage.setItem(
      "easyads_reference_templates_cache_v1",
      JSON.stringify({
        entries: {
          "category=&keyword=&tags=&limit=30": {
            cachedAt: "2026-06-11T00:00:00.000Z",
            items: [
              {
                templateId: "cached_reference_1",
                title: "캐시된 샘플",
                description: "기다림 없이 먼저 보이는 샘플",
                category: "cafe",
                tags: ["캐시", "카페"],
                businessTypes: ["cafe"],
                adFormats: ["instagram_feed"],
                platforms: ["instagram"],
                aspectRatio: "1:1",
                thumbnailUrl: "http://127.0.0.1:4000/api/references/temp-assets/cache/ref.png",
                previewUrl: "http://127.0.0.1:4000/api/references/temp-assets/cache/ref.png",
                styleKeywords: ["quick"],
                colorPalette: ["#5AB4F2", "#FFFFFF"],
                layoutHint: "center_product",
                typographyHint: "bold_headline",
                popularityScore: 0.9,
                isSaved: false
              }
            ]
          }
        }
      })
    );
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="reference" />);

    expect(screen.getByText("캐시된 샘플")).toBeTruthy();
    expect(screen.queryByLabelText("샘플 목록 불러오는 중")).toBeNull();
    await waitFor(() =>
      expect(api.listReferenceTemplates).toHaveBeenCalledWith({
        keyword: "",
        category: "",
        tags: [],
        limit: 30
      })
    );
  });

  it("caps stored reference template cache entries to the newest queries", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.listReferenceTemplates).mockClear();
    const existingEntries = Object.fromEntries(
      Array.from({ length: 20 }, (_, index) => [
        `category=cached_${index}&keyword=&tags=&limit=30`,
        {
          cachedAt: `2000-01-${String(index + 1).padStart(2, "0")}T00:00:00.000Z`,
          items: [{ templateId: `cached_${index}`, title: `오래된 캐시 ${index}` }]
        }
      ])
    );
    window.localStorage.setItem(
      "easyads_reference_templates_cache_v1",
      JSON.stringify({ entries: existingEntries })
    );
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="reference" />);
    await waitForReferenceTemplatesLoaded();

    await waitFor(() => {
      const stored = JSON.parse(window.localStorage.getItem("easyads_reference_templates_cache_v1") ?? "{}") as {
        entries?: Record<string, unknown>;
      };
      const entries = stored.entries ?? {};
      expect(Object.keys(entries)).toHaveLength(20);
      expect(entries["category=&keyword=&tags=&limit=30"]).toBeTruthy();
      expect(entries["category=cached_0&keyword=&tags=&limit=30"]).toBeUndefined();
    });
  });

  it("debounces reference gallery search requests", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.listReferenceTemplates).mockClear();
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="reference" />);
    await waitForReferenceTemplatesLoaded();
    vi.mocked(api.listReferenceTemplates).mockClear();

    vi.useFakeTimers();
    try {
      fireEvent.change(screen.getByLabelText("샘플 검색어"), { target: { value: "수" } });
      fireEvent.change(screen.getByLabelText("샘플 검색어"), { target: { value: "수박" } });

      expect(api.listReferenceTemplates).not.toHaveBeenCalled();

      await act(async () => {
        vi.advanceTimersByTime(299);
      });
      expect(api.listReferenceTemplates).not.toHaveBeenCalled();

      await act(async () => {
        vi.advanceTimersByTime(1);
        await Promise.resolve();
      });

      vi.useRealTimers();
      await waitFor(() =>
        expect(api.listReferenceTemplates).toHaveBeenCalledWith({
          keyword: "수박",
          category: "",
          tags: ["수박"],
          limit: 30
        })
      );
    } finally {
      vi.useRealTimers();
    }
  });


  it("keeps reference search results selectable when image urls are unavailable", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.listReferenceTemplates).mockResolvedValueOnce({
      items: [
        {
          templateId: "seed_no_image_reference",
          title: "이미지 없는 seed 샘플",
          description: "이미지 URL이 아직 없는 내부 메타데이터",
          category: "cafe",
          tags: ["카페"],
          businessTypes: ["cafe"],
          adFormats: ["instagram_feed"],
          platforms: ["instagram"],
          aspectRatio: "1:1",
          thumbnailUrl: null,
          previewUrl: null,
          styleKeywords: ["mock"],
          colorPalette: ["#FFFFFF"],
          layoutHint: "placeholder",
          typographyHint: "placeholder",
          popularityScore: 0.9,
          isSaved: false
        }
      ],
      pagination: { limit: 40, offset: 0, total: 1, hasMore: false }
    });
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="reference" />);

    await waitFor(() => expect(screen.getByText("이미지 없는 seed 샘플")).toBeTruthy());
    expect(screen.queryByText("조건에 맞는 샘플이 없어요")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "이미지 없는 seed 샘플 상세 보기" }));

    expect(navigationMock.push).toHaveBeenCalledWith("/reference/seed_no_image_reference");
  });

  it("opens the studio entry and dashboard tabs from the home dashboard", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient />);

    fireEvent.click(screen.getByRole("button", { name: /광고 만들기/ }));
    expect(screen.getByText("어떻게 시작할까요?")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /보관함/ }));
    expect(screen.getByText("내 찰떡 광고")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /마이페이지/ }));
    expect(navigationMock.push).toHaveBeenCalledWith("/my");
    expect(screen.getByRole("heading", { name: "마이페이지" })).toBeTruthy();
  });

  it("shows studio workspaces and opens the selected thread", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.listChatThreads).mockResolvedValueOnce({
      success: true,
      threads: [
        {
          thread_id: "thread_strawberry",
          title: "딸기라떼 신메뉴 광고",
          status: "draft",
          brand_kit_id: null,
          project_id: null,
          final_brief: {},
          active_job_id: null,
          has_final_output: false,
          last_message_at: "2026-06-07T00:00:00+00:00",
          archived_at: null,
          created_at: "2026-06-07T00:00:00+00:00",
          updated_at: "2026-06-07T00:00:00+00:00"
        }
      ],
      total: 1
    });
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="studio" />);

    await waitFor(() => expect(screen.getByText("딸기라떼 신메뉴 광고")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "이어하기" }));

    expect(navigationMock.push).toHaveBeenCalledWith("/generate/chat?threadId=thread_strawberry");
  });

  it("shows a workspace load error instead of an empty studio state", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.listChatThreads).mockRejectedValueOnce(new Error("Failed to fetch"));

    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="studio" />);

    await waitFor(() => expect(screen.getByText("작업방을 불러오지 못했어요")).toBeTruthy());
    expect(screen.getByText("작업방 서버에 연결하지 못했어요. 잠시 후 다시 시도해 주세요.")).toBeTruthy();
    expect(screen.queryByText("아직 이어갈 작업방이 없어요")).toBeNull();
    expect(screen.getByRole("button", { name: "다시 불러오기" })).toBeTruthy();
  });

  it("returns from chat start to the studio entry instead of browser history", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="studio" />);

    fireEvent.click(screen.getByRole("button", { name: /새 작업/ }));
    expect(screen.getByText("대화로 찰떡 이미지 만들기")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "이전 화면" }));

    expect(navigationMock.back).not.toHaveBeenCalled();
    expect(navigationMock.push).toHaveBeenCalledWith("/studio");
  });

  it("returns from home chat quick start back to the home dashboard", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient />);

    fireEvent.click(screen.getByRole("button", { name: /대화로 시작하기/ }));
    expect(screen.getByText("대화로 찰떡 이미지 만들기")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "이전 화면" }));

    expect(navigationMock.back).not.toHaveBeenCalled();
    expect(navigationMock.push).toHaveBeenCalledWith("/");
  });

  it("archives a studio workspace after a delete warning", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.listChatThreads).mockResolvedValueOnce({
      success: true,
      threads: [
        {
          thread_id: "thread_strawberry",
          title: "딸기라떼 신메뉴 광고",
          status: "draft",
          brand_kit_id: null,
          project_id: null,
          final_brief: {},
          active_job_id: null,
          has_final_output: false,
          last_message_at: "2026-06-07T00:00:00+00:00",
          archived_at: null,
          created_at: "2026-06-07T00:00:00+00:00",
          updated_at: "2026-06-07T00:00:00+00:00"
        }
      ],
      total: 1
    });
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="studio" />);

    await waitFor(() => expect(screen.getByText("딸기라떼 신메뉴 광고")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "딸기라떼 신메뉴 광고 작업방 삭제" }));
    expect(screen.getByRole("dialog", { name: "이 작업방을 삭제할까요?" })).toBeTruthy();
    expect(screen.getByText("완성된 이미지는 보관함에 남아요.", { exact: false })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "삭제" }));

    await waitFor(() => expect(api.archiveChatThread).toHaveBeenCalledWith("thread_strawberry"));
    await waitFor(() => expect(screen.queryByText("딸기라떼 신메뉴 광고")).toBeNull());
    expect(screen.getByText("아직 이어갈 작업방이 없어요")).toBeTruthy();
  });

  it("opens the photo flow from the home dashboard", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient />);

    fireEvent.click(screen.getByRole("button", { name: /내 사진으로 만들기/ }));

    expect(navigationMock.push).toHaveBeenCalledWith("/generate/photo");
    expect(screen.getByText("내 사진으로 만들기")).toBeTruthy();
    expect(screen.getByText("광고에 쓸 사진을 올려주세요")).toBeTruthy();
    expect(screen.getByRole("button", { name: "사진 선택하기" })).toBeTruthy();
  });

  it("returns from photo start to the previous app surface without browser history", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="studio" />);

    fireEvent.click(screen.getByRole("button", { name: /내 사진으로 만들기/ }));
    expect(screen.getByText("내 사진으로 만들기")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "이전 화면" }));

    expect(navigationMock.back).not.toHaveBeenCalled();
    expect(navigationMock.push).toHaveBeenCalledWith("/studio");
  });

  it("returns from the photo fallback chat start back to the photo flow", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="studio" />);

    fireEvent.click(screen.getByRole("button", { name: /내 사진으로 만들기/ }));
    expect(screen.getByText("내 사진으로 만들기")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "이미지 없이 대화로 시작하기" }));
    expect(screen.getByText("대화로 찰떡 이미지 만들기")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "이전 화면" }));

    expect(navigationMock.back).not.toHaveBeenCalled();
    expect(navigationMock.push).toHaveBeenCalledWith("/generate/photo");
  });

  it("shows a saved brand kit on the home and my page surfaces", async () => {
    window.localStorage.setItem(
      BRAND_KIT_STORAGE_KEY,
      JSON.stringify({
        businessName: "연남 테스트 카페",
        businessType: "카페",
        region: "연남동",
        sns: "@test_cafe",
        tones: ["따뜻한"],
        colors: ["#FFD7C9"],
        phrases: ["예약은 DM 주세요"],
        products: ["라떼"],
        status: "saved",
        updatedAt: "2026-06-01T00:00:00.000Z"
      })
    );
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    const { rerender } = render(<ChatGenerateClient />);

    await waitFor(() => expect(screen.getByText("브랜드 파일이 연결되어 있어요")).toBeTruthy());
    expect(screen.getByText(/연남 테스트 카페/)).toBeTruthy();

    rerender(<ChatGenerateClient initialSurface="my" />);

    await waitFor(() => expect(screen.getByText("브랜드 파일 사용 중")).toBeTruthy());
    expect(screen.getByText(/연남 테스트 카페/)).toBeTruthy();
  });

  it("opens the brand kit start screen from the disconnected my page banner", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="my" />);

    fireEvent.click(screen.getByRole("button", { name: /브랜드 파일 연결 전/ }));

    expect(navigationMock.push).toHaveBeenCalledWith("/brand/kit");
    expect(navigationMock.push).not.toHaveBeenCalledWith("/brand/kit/info");
  });

  it("does not expose an ambiguous see-all menu link on my page", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="my" />);

    expect(screen.queryByRole("button", { name: "전체 보기" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: /사용량 정보/ }));
    expect(navigationMock.push).toHaveBeenCalledWith("/my/usage");
  });

  it("sends saved brand kit context with chat generation requests", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.createGenerationJob).mockClear();
    window.localStorage.setItem(
      BRAND_KIT_STORAGE_KEY,
      JSON.stringify({
        businessName: "연남 테스트 카페",
        businessType: "카페",
        region: "연남동",
        sns: "@test_cafe",
        tones: ["따뜻한"],
        colors: ["#FFD7C9"],
        phrases: ["예약은 DM 주세요"],
        products: ["대표 메뉴"],
        status: "saved",
        updatedAt: "2026-06-01T00:00:00.000Z"
      })
    );
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" />);

    fireEvent.change(screen.getByLabelText("광고 요청 입력"), { target: { value: "광고 만들어줘" } });
    fireEvent.click(screen.getByLabelText("요청 보내기"));

    await waitFor(() => expect(api.createGenerationJob).toHaveBeenCalled());
    const request = vi.mocked(api.createGenerationJob).mock.calls[0][0];
    expect(request.userInput).toContain("광고 만들어줘");
    expect(request.userInput).toContain("가게 이름: 연남 테스트 카페");
    expect(request.userInput).toContain("브랜드 톤: 따뜻한");
  });

  it("renders dashboard surfaces from route props", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    const { rerender } = render(<ChatGenerateClient initialSurface="studio" />);
    expect(screen.getByText("어떻게 시작할까요?")).toBeTruthy();

    rerender(<ChatGenerateClient initialSurface="reference" />);
    expect(screen.getByText("SAMPLE GALLERY")).toBeTruthy();

    rerender(<ChatGenerateClient initialSurface="ads" />);
    expect(screen.getByText("내 찰떡 광고")).toBeTruthy();

    rerender(<ChatGenerateClient initialSurface="my" />);
    expect(screen.getByRole("heading", { name: "마이페이지" })).toBeTruthy();

    rerender(<ChatGenerateClient initialSurface="brand" />);
    expect(screen.queryByRole("heading", { name: "마이페이지" })).toBeNull();

    rerender(<ChatGenerateClient initialSurface="photo" />);
    expect(screen.getByText("내 사진으로 만들기")).toBeTruthy();
    expect(screen.getByText("광고에 쓸 사진을 올려주세요")).toBeTruthy();
  });

  it("shows an empty generated result state when the complete route has no backend brief", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" initialStage="complete" />);

    await waitFor(() => expect(screen.getByText("생성 요청 내역이 없어요")).toBeTruthy());
    expect(screen.queryByText("봄을 닮은 한 잔, 딸기라떼 출시")).toBeNull();
    expect(screen.queryByText("카페")).toBeNull();
    expect(screen.queryByText("감성적인")).toBeNull();
    expect(screen.queryByText("인스타 피드")).toBeNull();
    expect(screen.queryByRole("button", { name: /시안 편집하기/ })).toBeNull();
    expect(screen.getByRole("button", { name: /보관함 연결 대기 중/ }).hasAttribute("disabled")).toBe(true);
  });

  it("restores the generated result route from a job id", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.getGenerationJob).mockResolvedValueOnce({
      success: true,
      job: {
        job_id: "generation_job_route",
        thread_id: "thread_route",
        status: "done",
        progress: { progress_percent: 100, current_stage: "completed" },
        result_payload: {
          schema_version: "result_artifact_v1",
          job_id: "generation_job_route",
          preview_image_url: "/api/generated-assets?path=data%2Foutputs%2Fgeneration_job_route%2Ffinal_0.png",
          download_url: "/api/generated-assets?path=data%2Foutputs%2Fgeneration_job_route%2Ffinal_0.png",
          final_image_path: "data/outputs/generation_job_route/final_0.png",
          engine: "gpt_image_1"
        },
        metadata: { selected_engine_label: "GPT-image-1" },
        created_at: "2026-06-05T00:00:00.000Z",
        updated_at: "2026-06-05T00:00:00.000Z"
      }
    });
    vi.mocked(api.getChatThreadState).mockResolvedValueOnce({ success: true, snapshot: null });
    vi.mocked(api.getChatThreadMessages).mockResolvedValueOnce({ success: true, messages: [], total: 0 });
    searchParamsMock.value = new URLSearchParams("jobId=generation_job_route&threadId=thread_route");
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" initialStage="complete" />);

    await waitFor(() => expect(api.getGenerationJob).toHaveBeenCalledWith("generation_job_route"));
    await waitFor(() => expect(screen.getByText("광고 이미지 생성이 완료됐어요")).toBeTruthy());
    expect(screen.queryByText("생성 요청 내역이 없어요")).toBeNull();
    expect(screen.getByText("GPT-image-1")).toBeTruthy();
  });

  it("shows the failed generation reason instead of an empty result shell", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.getGenerationJob).mockResolvedValueOnce({
      success: true,
      job: {
        job_id: "generation_job_failed_route",
        thread_id: "thread_failed_route",
        status: "failed",
        progress: { progress_percent: 100, current_stage: "failed" },
        result_payload: null,
        error: { message: "GPT-image-1 generation is disabled." },
        metadata: { selected_engine_label: "GPT-image-1" },
        created_at: "2026-06-05T00:00:00.000Z",
        updated_at: "2026-06-05T00:00:00.000Z"
      }
    });
    vi.mocked(api.getChatThreadState).mockResolvedValueOnce({ success: true, snapshot: null });
    vi.mocked(api.getChatThreadMessages).mockResolvedValueOnce({ success: true, messages: [], total: 0 });
    searchParamsMock.value = new URLSearchParams("jobId=generation_job_failed_route&threadId=thread_failed_route");
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" initialStage="complete" />);

    await waitFor(() => expect(screen.getByText("이미지 생성에 실패했어요")).toBeTruthy());
    expect(screen.getAllByText("GPT-image-1 generation is disabled.").length).toBeGreaterThan(0);
    expect(screen.queryByText("생성 요청 내역이 없어요")).toBeNull();
  });

  it("restores complete route context without rendering a direct generated image", async () => {
    window.sessionStorage.setItem(
      "easyads_chat_flow_snapshot_v1",
      JSON.stringify({
        prompt: "우리 카페 딸기라떼 신메뉴 광고 만들어줘",
        jobId: "job_1",
        threadId: "thread_1",
        context: {
          businessType: "카페",
          itemOrService: "딸기라떼",
          promotionGoal: "신메뉴 출시"
        },
        copyCandidates: [{ id: "copy_1", headline: "봄을 닮은 한 잔, 딸기라떼 출시" }],
        selectedCopyId: "copy_1",
        selectedChannelId: "instagram-feed",
        selectedTone: "감성적인",
        customDirection: "",
        brief: {
          purpose: "신메뉴 출시",
          item: "딸기라떼",
          copy: "봄을 닮은 한 잔, 딸기라떼 출시",
          tone: "감성적인 카페 무드",
          channel: "인스타 피드 (1:1)",
          imageDirection: "크림톤 배경",
          finalImagePath: "/api/generated-assets?path=data%2Foutputs%2Fjob_1%2Ffinal_composite.png"
        }
      })
    );
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" initialStage="complete" />);

    await waitFor(() => expect(screen.getByText("이미지를 만들고 있어요")).toBeTruthy());
    expect(screen.getByText("딸기라떼")).toBeTruthy();
    expect(screen.getByText("완성되면 보관함에 자동으로 저장돼요. 잠시만 기다려주세요.")).toBeTruthy();
    expect(screen.getByText("미리보기는 완성 후 표시돼요")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "딸기라떼 더 크게" })).toBeNull();
    expect(screen.queryByRole("button", { name: "핑크톤 줄이기" })).toBeNull();
    expect(document.querySelector('img[src*="generated-assets"][src*="final_composite.png"]')).toBeNull();
  });

  it("does not save generated results directly from the completion screen", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.saveArchiveItem).mockClear();
    window.sessionStorage.setItem(
      "easyads_chat_flow_snapshot_v1",
      JSON.stringify({
        prompt: "우리 카페 딸기라떼 신메뉴 광고 만들어줘",
        jobId: "job_1",
        threadId: "thread_1",
        context: {
          businessType: "카페",
          itemOrService: "딸기라떼",
          promotionGoal: "신메뉴 출시"
        },
        copyCandidates: [{ id: "copy_1", headline: "봄을 닮은 한 잔, 딸기라떼 출시" }],
        selectedCopyId: "copy_1",
        selectedChannelId: "instagram-feed",
        selectedTone: "감성적인",
        customDirection: "",
        brief: {
          purpose: "신메뉴 출시",
          item: "딸기라떼",
          copy: "봄을 닮은 한 잔, 딸기라떼 출시",
          tone: "감성적인 카페 무드",
          channel: "인스타 피드 (1:1)",
          imageDirection: "크림톤 배경",
          finalImagePath: "/api/generated-assets?path=data%2Foutputs%2Fjob_1%2Ffinal_composite.png"
        }
      })
    );
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" initialStage="complete" />);

    await waitFor(() => expect(screen.getByText("이미지를 만들고 있어요")).toBeTruthy());
    expect(screen.queryByLabelText("봄을 닮은 한 잔, 딸기라떼 출시 저장")).toBeNull();
    expect(api.saveArchiveItem).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: /보관함에서 기다리기/ }).hasAttribute("disabled")).toBe(false);
  });

  it("keeps the archive CTA disabled when the complete route has no browser-usable result URL", async () => {
    window.sessionStorage.setItem(
      "easyads_chat_flow_snapshot_v1",
      JSON.stringify({
        prompt: "우리 카페 딸기라떼 신메뉴 광고 만들어줘",
        jobId: "job_1",
        threadId: "thread_1",
        context: {
          businessType: "카페",
          itemOrService: "딸기라떼",
          promotionGoal: "신메뉴 출시"
        },
        copyCandidates: [{ id: "copy_1", headline: "봄을 닮은 한 잔, 딸기라떼 출시" }],
        selectedCopyId: "copy_1",
        selectedChannelId: "instagram-feed",
        selectedTone: "감성적인",
        customDirection: "",
        brief: {
          purpose: "신메뉴 출시",
          item: "딸기라떼",
          copy: "봄을 닮은 한 잔, 딸기라떼 출시",
          tone: "감성적인 카페 무드",
          channel: "인스타 피드 (1:1)",
          imageDirection: "크림톤 배경",
          finalImagePath: "/api/generated-assets?path=data%2Foutputs%2Fjob_1%2Ffinal_composite.png"
        }
      })
    );
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" initialStage="complete" />);

    await waitFor(() => expect(screen.getByText("이미지를 만들고 있어요")).toBeTruthy());
    expect(screen.queryByText("New Strawberry Latte")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: /보관함에서 기다리기/ }));
    expect(navigationMock.push).toHaveBeenCalledWith("/ads");
    await flushAsyncEffects();
  });

  it("opens the selected generated archive item instead of the active complete result", async () => {
    window.localStorage.setItem(
      "easyads_generated_creatives_v1",
      JSON.stringify([
        {
          id: "generated-job_latest",
          title: "최근 생성 광고",
          subtitle: "카페 · 인스타 피드",
          format: "1:1",
          imageUrl: "/api/generated-assets?path=data%2Foutputs%2Fjob_latest%2Ffinal_composite.png",
          tone: "strawberry",
          badge: "실제 생성",
          status: "saved",
          channel: "인스타 피드",
          fileName: "final_composite.png",
          fileType: "PNG",
          storage: "보관함",
          savedAt: "방금 생성",
          tags: ["카페", "딸기라떼"]
        },
        {
          id: "generated-job_selected",
          title: "직접 클릭한 생성 광고",
          subtitle: "베이커리 · 포스터",
          format: "4:5",
          imageUrl: "/api/generated-assets?path=data%2Foutputs%2Fjob_selected%2Ffinal_composite.png",
          tone: "cream",
          badge: "실제 생성",
          status: "saved",
          channel: "포스터",
          fileName: "final_composite.png",
          fileType: "PNG",
          storage: "보관함",
          savedAt: "방금 생성",
          tags: ["베이커리", "포스터"]
        }
      ])
    );
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="ads" />);

    await waitFor(() => expect(screen.getByText("직접 클릭한 생성 광고")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "직접 클릭한 생성 광고 실제 생성 결과 보기" }));

    expect(navigationMock.push).toHaveBeenCalledWith("/ads/generated-job_selected");
    expect(navigationMock.push).not.toHaveBeenCalledWith("/generate/chat/complete");
  });

  it("opens archive search from the header icon and filters generated results", async () => {
    window.localStorage.setItem(
      "easyads_generated_creatives_v1",
      JSON.stringify([
        {
          id: "generated-job_latest",
          title: "최근 생성 광고",
          subtitle: "카페 · 인스타 피드",
          format: "1:1",
          imageUrl: "/api/generated-assets?path=data%2Foutputs%2Fjob_latest%2Ffinal_composite.png",
          tone: "strawberry",
          badge: "실제 생성",
          status: "saved",
          channel: "인스타 피드",
          fileName: "final_composite.png",
          fileType: "PNG",
          storage: "브라우저 임시 보관함",
          savedAt: "방금 생성",
          tags: ["카페", "딸기라떼"]
        },
        {
          id: "generated-job_selected",
          title: "직접 클릭한 생성 광고",
          subtitle: "베이커리 · 포스터",
          format: "4:5",
          imageUrl: "/api/generated-assets?path=data%2Foutputs%2Fjob_selected%2Ffinal_composite.png",
          tone: "cream",
          badge: "실제 생성",
          status: "saved",
          channel: "포스터",
          fileName: "final_composite.png",
          fileType: "PNG",
          storage: "브라우저 임시 보관함",
          savedAt: "방금 생성",
          tags: ["베이커리", "포스터"]
        }
      ])
    );
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="ads" />);

    await waitFor(() => expect(screen.getByText("직접 클릭한 생성 광고")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "보관함 검색 열기" }));
    const searchInput = screen.getByLabelText("보관함 검색어") as HTMLInputElement;
    expect(document.activeElement).toBe(searchInput);

    fireEvent.change(searchInput, { target: { value: "베이커리" } });

    expect(screen.getByText("직접 클릭한 생성 광고")).toBeTruthy();
    expect(screen.queryByText("최근 생성 광고")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "보관함 검색어 지우기" }));
    expect(screen.getByText("최근 생성 광고")).toBeTruthy();
  });

  it("renders a persisted archive detail through the direct archive API", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.getArchiveItem).mockClear();
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { AdSaveFlowStep } = await import("@/components/generate/AdSaveFlowStep");

    render(<AdSaveFlowStep creativeId="archive_db_detail" step="detail" />);

    await waitFor(() => expect(api.getArchiveItem).toHaveBeenCalledWith("archive_db_detail"));
    await waitFor(() => expect(screen.getByText("DB 상세 광고")).toBeTruthy());
    expect(screen.getByText("생성 이미지 보기")).toBeTruthy();
    expect(document.querySelector('img[src*="archive-db-detail.png"]')).toBeTruthy();
    expect(screen.queryByText("보관함에서 이 항목을 찾지 못했어요")).toBeNull();
  });

  it("renders the selected generated archive detail from session storage", async () => {
    window.localStorage.setItem(
      "easyads_generated_creatives_v1",
      JSON.stringify([
        {
          id: "generated-job_latest",
          title: "최근 생성 광고",
          subtitle: "카페 · 인스타 피드",
          format: "1:1",
          imageUrl: "/api/generated-assets?path=data%2Foutputs%2Fjob_latest%2Ffinal_composite.png",
          tone: "strawberry",
          badge: "실제 생성",
          status: "saved",
          channel: "인스타 피드",
          fileName: "final_composite.png",
          fileType: "PNG",
          storage: "보관함",
          savedAt: "방금 생성",
          tags: ["카페", "딸기라떼"]
        },
        {
          id: "generated-job_selected",
          title: "직접 클릭한 생성 광고",
          subtitle: "베이커리 · 포스터",
          format: "4:5",
          imageUrl: "/api/generated-assets?path=data%2Foutputs%2Fjob_selected%2Ffinal_composite.png",
          tone: "cream",
          badge: "실제 생성",
          status: "saved",
          channel: "포스터",
          fileName: "final_composite.png",
          fileType: "PNG",
          storage: "보관함",
          savedAt: "방금 생성",
          tags: ["베이커리", "포스터"]
        }
      ])
    );
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { AdSaveFlowStep } = await import("@/components/generate/AdSaveFlowStep");

    render(<AdSaveFlowStep creativeId="generated-job_selected" step="detail" />);

    await waitFor(() => expect(screen.getByText("생성 이미지 보기")).toBeTruthy());
    await waitFor(() => expect(screen.getByText("직접 클릭한 생성 광고")).toBeTruthy());
    expect(screen.getByText("생성된 이미지만 확인하고 다운로드할 수 있어요.")).toBeTruthy();
    expect(screen.getByRole("button", { name: /이미지 다운로드/ })).toBeTruthy();
    expect(screen.queryByText("최근 생성 광고")).toBeNull();
    expect(screen.queryByText("빠른 수정")).toBeNull();
    expect(screen.queryByRole("button", { name: /이 시안 저장하기/ })).toBeNull();
    expect(document.querySelector('img[src*="job_selected"]')).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /이미지 다운로드/ }));
    expect(screen.getByText("실제 파일 저장 연결 후 다운로드가 활성화돼요.")).toBeTruthy();
  });

  it("prefers session image data over static mock data when archive ids overlap", async () => {
    window.localStorage.setItem(
      "easyads_generated_creatives_v1",
      JSON.stringify([
        {
          id: "generated-result-1",
          title: "실제 생성 result-1",
          subtitle: "카페 · 인스타 피드",
          format: "1:1",
          imageUrl: "/api/generated-assets?path=data%2Foutputs%2Freal_result_1%2Ffinal_composite.png",
          tone: "strawberry",
          badge: "실제 생성",
          status: "saved",
          channel: "인스타 피드",
          fileName: "final_composite.png",
          fileType: "PNG",
          storage: "내 광고 보관함",
          savedAt: "방금 생성",
          tags: ["카페", "딸기라떼"]
        }
      ])
    );
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { AdSaveFlowStep } = await import("@/components/generate/AdSaveFlowStep");

    render(<AdSaveFlowStep creativeId="result-1" step="detail" />);

    await waitFor(() => expect(screen.getByText("생성 이미지 보기")).toBeTruthy());
    expect(screen.getByText("실제 생성 result-1")).toBeTruthy();
    expect(screen.queryByText("봄을 닮은 한 잔")).toBeNull();
    expect(document.querySelector('img[src*="real_result_1"]')).toBeTruthy();
  });

  it("shows a mock download action for generated archive items", async () => {
    window.localStorage.setItem(
      "easyads_generated_creatives_v1",
      JSON.stringify([
        {
          id: "generated-job_selected",
          title: "직접 클릭한 생성 광고",
          subtitle: "베이커리 · 포스터",
          format: "4:5",
          imageUrl: "/api/generated-assets?path=data%2Foutputs%2Fjob_selected%2Ffinal_composite.png",
          tone: "cream",
          badge: "실제 생성",
          status: "saved",
          channel: "포스터",
          fileName: "final_composite.png",
          fileType: "PNG",
          storage: "보관함",
          savedAt: "방금 생성",
          tags: ["베이커리", "포스터"]
        }
      ])
    );
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="ads" />);

    await waitFor(() => expect(screen.getByText("직접 클릭한 생성 광고")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "직접 클릭한 생성 광고 더보기" }));

    expect(screen.getByRole("menuitem", { name: "다운로드" })).toBeTruthy();
    fireEvent.click(screen.getByRole("menuitem", { name: "다운로드" }));

    expect(screen.getByText("직접 클릭한 생성 광고 다운로드는 실제 파일 저장 연결 후 활성화돼요.")).toBeTruthy();
  });

  it("loads and deletes persisted archive items through the archive API", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.listArchiveItems).mockResolvedValueOnce({
      items: [
        {
          adId: "archive_db_1",
          jobId: "job_db_1",
          title: "DB 저장 광고",
          imageUrl: "/api/generated-assets?path=data%2Foutputs%2Fjob_db_1%2Ffinal.png",
          thumbnailUrl: "/api/generated-assets?path=data%2Foutputs%2Fjob_db_1%2Ffinal.png",
          status: "saved",
          adFormat: "1:1",
          platform: "인스타 피드",
          source: "generated",
          savedAt: "2026-06-05T00:00:00+00:00",
          metadata: {
            subtitle: "카페 · 인스타 피드",
            fileName: "final.png",
            fileType: "PNG",
            tags: ["카페", "피드"]
          }
        }
      ],
      pagination: { limit: 20, offset: 0, total: 1, hasMore: false }
    });
    vi.mocked(api.updateArchiveItem).mockClear();
    vi.mocked(api.deleteArchiveItem).mockClear();
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="ads" />);

    await waitFor(() => expect(api.listArchiveItems).toHaveBeenCalledWith({ limit: 20, includeTotal: false }));
    await waitFor(() => expect(screen.getByText("DB 저장 광고")).toBeTruthy());

    fireEvent.click(screen.getByRole("button", { name: "DB 저장 광고 즐겨찾기" }));
    await waitFor(() => expect(api.updateArchiveItem).toHaveBeenCalledWith("archive_db_1", { status: "favorite" }));
    await waitFor(() => expect(screen.getByText("DB 저장 광고를 즐겨찾기에 추가했어요.")).toBeTruthy());

    fireEvent.click(screen.getByRole("button", { name: "DB 저장 광고 실제 생성 결과 보기" }));
    expect(navigationMock.push).toHaveBeenCalledWith("/ads/archive_db_1");

    fireEvent.click(screen.getByRole("button", { name: "DB 저장 광고 더보기" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "삭제" }));

    await waitFor(() => expect(api.deleteArchiveItem).toHaveBeenCalledWith("archive_db_1"));
    await waitFor(() => expect(screen.queryByRole("button", { name: "DB 저장 광고 실제 생성 결과 보기" })).toBeNull());
    expect(screen.getByText("DB 저장 광고 항목을 보관함에서 삭제했어요.")).toBeTruthy();
  });

  it("shows cached archive items immediately while refreshing persisted archive items", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.listArchiveItems).mockClear();
    vi.mocked(api.listArchiveItems).mockReturnValueOnce(new Promise(() => undefined));
    window.localStorage.setItem(
      "easyads_archive_creatives_cache_v1",
      JSON.stringify({
        cachedAt: "2026-06-11T00:00:00.000Z",
        creatives: [
          {
            id: "archive_cached_1",
            title: "캐시된 광고",
            subtitle: "카페 · 인스타 피드",
            format: "1:1",
            imageUrl: "/api/generated-assets?path=data%2Foutputs%2Fjob_cached%2Ffinal.png",
            date: "2026. 06. 11.",
            tone: "mint",
            badge: "보관함",
            status: "saved",
            channel: "인스타 피드",
            fileName: "final.png",
            fileType: "PNG",
            storage: "내 광고 보관함",
            savedAt: "2026. 06. 11.",
            tags: ["카페"]
          }
        ]
      })
    );
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="ads" />);

    expect(screen.getByText("캐시된 광고")).toBeTruthy();
    expect(screen.queryByText("보관함을 불러오는 중이에요")).toBeNull();
    await waitFor(() => expect(api.listArchiveItems).toHaveBeenCalledWith({ limit: 20, includeTotal: false }));
  });

  it("pushes stable URLs when top-level tabs are selected", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient />);

    fireEvent.click(screen.getByRole("button", { name: /광고 만들기/ }));
    expect(navigationMock.push).toHaveBeenCalledWith("/studio");

    fireEvent.click(screen.getAllByRole("button", { name: /찾기/ }).at(-1)!);
    expect(navigationMock.push).toHaveBeenCalledWith("/reference");
    await waitForReferenceTemplatesLoaded();
  });

  it("opens studio from the empty archive new ad CTA", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="ads" />);

    await waitFor(() => expect(screen.getByRole("button", { name: "새 광고 만들기" })).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "새 광고 만들기" }));

    expect(navigationMock.push).toHaveBeenCalledWith("/studio");
    expect(navigationMock.push).not.toHaveBeenCalledWith("/generate/chat");
  });

  it("shows archive load errors separately from a true empty archive", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.listArchiveItems).mockClear();
    vi.mocked(api.listArchiveItems).mockRejectedValueOnce(new Error("archive unavailable"));
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="ads" />);

    await waitFor(() => expect(screen.getByText("보관함을 불러오지 못했어요")).toBeTruthy());
    expect(screen.queryByText("아직 저장된 실제 생성 결과가 없어요")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "다시 불러오기" }));

    await waitFor(() => expect(api.listArchiveItems).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.getByText("아직 저장된 실제 생성 결과가 없어요")).toBeTruthy());
  });

  it("offers history and flow-back escape routes from chat start", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" />);

    fireEvent.click(screen.getByRole("button", { name: "이전 대화" }));
    expect(await screen.findByRole("heading", { name: "이전 대화 기록" })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "이전 화면" }));
    expect(screen.getByText("대화로 찰떡 이미지 만들기")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "이전 화면" }));
    expect(navigationMock.back).not.toHaveBeenCalled();
    expect(navigationMock.push).toHaveBeenCalledWith("/studio");
  });

  it("shows a history load error instead of an empty previous chat state", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.listChatThreads).mockRejectedValueOnce(new Error("Supabase auth configuration is missing"));
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" />);

    fireEvent.click(screen.getByRole("button", { name: "이전 대화" }));

    expect(await screen.findByRole("heading", { name: "이전 대화 기록" })).toBeTruthy();
    await waitFor(() => expect(screen.getByText("이전 대화 기록을 불러오지 못했어요")).toBeTruthy());
    expect(screen.getByText("로그인 상태를 확인하지 못했어요. 다시 로그인한 뒤 작업방을 불러와 주세요.")).toBeTruthy();
    expect(screen.queryByText("이전 대화 기록이 없어요")).toBeNull();
  });

  it("shows realistic creative labels in reference cards", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="reference" />);

    await waitFor(() => expect(screen.getByText("수박주스 블루 여름 피드")).toBeTruthy());
    expect(screen.queryByText("임시 샘플")).toBeNull();
    expect(screen.queryByText("테스트용 샘플이 포함되어 있어요. 마음에 드는 스타일을 골라 다음 광고에 참고할 수 있어요.")).toBeNull();
    expect(screen.queryByText("이미지 없는 seed 샘플")).toBeNull();
    expect(screen.getByText("파란 배경과 큼직한 음료 중심의 여름 음료 샘플")).toBeTruthy();
    expect(screen.queryByText("SPRING SALE")).toBeNull();
  });

  it("shows pending feedback when a reference template save needs real archive storage", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="reference" />);

    await waitFor(() => expect(screen.getByText("수박주스 블루 여름 피드")).toBeTruthy());
    fireEvent.click(screen.getByLabelText("수박주스 블루 여름 피드 저장"));

    expect(screen.getByText("수박주스 블루 여름 피드 저장은 실제 보관함 연결 후 사용할 수 있어요.")).toBeTruthy();
    expect(screen.queryByText("수박주스 블루 여름 피드를 보관함에 저장했어요.")).toBeNull();
  });

  it("does not render sample archive ads and keeps brand kit actions available", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    const { rerender } = render(<ChatGenerateClient initialSurface="ads" />);

    expect(screen.queryByText("샘플 광고")).toBeNull();
    expect(screen.queryByText("아래 항목은 실제 생성 결과가 아니라 화면 확인용 샘플입니다. 보관함의 실제 결과와 분리해서 표시합니다.")).toBeNull();
    await waitFor(() => expect(screen.getByText("아직 저장된 실제 생성 결과가 없어요")).toBeTruthy());

    rerender(<ChatGenerateClient initialSurface="my" />);
    fireEvent.click(screen.getByRole("button", { name: /브랜드 파일 관리/ }));
    expect(navigationMock.push).toHaveBeenCalledWith("/brand/kit");
  });

  it("opens archive overflow actions and deletes an archive item", async () => {
    window.localStorage.setItem(
      "easyads_generated_creatives_v1",
      JSON.stringify([
        {
          id: "generated-job_selected",
          title: "직접 클릭한 생성 광고",
          subtitle: "베이커리 · 포스터",
          format: "4:5",
          imageUrl: "/api/generated-assets?path=data%2Foutputs%2Fjob_selected%2Ffinal_composite.png",
          tone: "cream",
          badge: "실제 생성",
          status: "saved",
          channel: "포스터",
          fileName: "final_composite.png",
          fileType: "PNG",
          storage: "보관함",
          savedAt: "방금 생성",
          tags: ["베이커리", "포스터"]
        }
      ])
    );
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="ads" />);

    await waitFor(() => expect(screen.getByText("직접 클릭한 생성 광고")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "직접 클릭한 생성 광고 더보기" }));

    expect(screen.getByRole("menu", { name: "직접 클릭한 생성 광고 작업 메뉴" })).toBeTruthy();
    expect(screen.getByRole("menuitem", { name: "결과 보기" })).toBeTruthy();
    expect(screen.getByRole("menuitem", { name: "비슷하게 만들기" })).toBeTruthy();

    fireEvent.click(screen.getByRole("menuitem", { name: "삭제" }));

    expect(screen.queryByRole("button", { name: "직접 클릭한 생성 광고 실제 생성 결과 보기" })).toBeNull();
    expect(screen.getByText("직접 클릭한 생성 광고 항목을 보관함에서 삭제했어요.")).toBeTruthy();
  });

  it("opens notifications from home and recent ads headers", async () => {
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    const { rerender } = render(<ChatGenerateClient />);

    fireEvent.click(screen.getByRole("button", { name: "알림" }));
    expect(navigationMock.push).toHaveBeenCalledWith("/notifications");

    rerender(<ChatGenerateClient initialSurface="ads" />);
    await flushAsyncEffects();
    fireEvent.click(screen.getByRole("button", { name: "알림" }));
    expect(navigationMock.push).toHaveBeenCalledWith("/notifications");
  });

  it("uploads a photo and routes backend generation into the chat flow", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.uploadPhotoAsset).mockClear();
    vi.mocked(api.startPhotoGeneration).mockClear();
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="photo" />);

    const file = new File([new Uint8Array([1, 2, 3])], "menu.png", { type: "image/png" });
    fireEvent.change(screen.getByLabelText("광고 사진 선택"), { target: { files: [file] } });
    fireEvent.change(screen.getByLabelText("사진 광고 요청 입력"), {
      target: { value: "이 사진으로 신메뉴 광고 만들어줘" }
    });
    fireEvent.click(screen.getByRole("button", { name: /사진 기반 생성 시작/ }));

    await waitFor(() => expect(api.uploadPhotoAsset).toHaveBeenCalledWith(file));
    await waitFor(() =>
      expect(api.startPhotoGeneration).toHaveBeenCalledWith({
        userInput: "이 사진으로 신메뉴 광고 만들어줘",
        sourceImagePath: "data/uploads/photo_1.png",
        copyGenerationMode: "suggest_candidates"
      })
    );
    expect(navigationMock.push).toHaveBeenCalledWith("/generate/chat");
    await waitFor(() => expect(screen.getByText("AI가 이렇게 이해했어요")).toBeTruthy());
    expect(screen.getByText("딸기라떼")).toBeTruthy();
    expect(screen.queryByText("AI 분석 결과")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "문구 고르기" }));
    expect(screen.getByText("채널과 방향을 골라주세요")).toBeTruthy();
    expect(screen.queryByText("사진 속 메뉴를 오늘의 신메뉴로")).toBeNull();
  });

  it("passes uploaded photo sourceImagePath to the final generation job", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.uploadPhotoAsset).mockClear();
    vi.mocked(api.startPhotoGeneration).mockClear();
    vi.mocked(api.createChatBrief).mockClear();
    vi.mocked(api.createGenerationJob).mockClear();
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="photo" />);

    const file = new File([new Uint8Array([1, 2, 3])], "menu.png", { type: "image/png" });
    fireEvent.change(screen.getByLabelText("광고 사진 선택"), { target: { files: [file] } });
    fireEvent.change(screen.getByLabelText("사진 광고 요청 입력"), {
      target: { value: "이 사진으로 신메뉴 광고 만들어줘" }
    });
    fireEvent.click(screen.getByRole("button", { name: /사진 기반 생성 시작/ }));

    await waitFor(() => expect(screen.getByText("AI가 이렇게 이해했어요")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "문구 고르기" }));
    fireEvent.click(screen.getByRole("button", { name: "브리프 확인하기" }));
    await waitFor(() => expect(screen.getByText("AI가 브리프를 정리했어요")).toBeTruthy());

    fireEvent.click(screen.getByText(/이 내용으로 이미지 생성/));

    await waitFor(() =>
      expect(api.createGenerationJob).toHaveBeenCalledWith(
        expect.objectContaining({
          sourceImagePath: "data/uploads/photo_1.png"
        })
      )
    );
  });

  it("routes photo generation directly to a backend brief in image-only mode", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.uploadPhotoAsset).mockClear();
    vi.mocked(api.startPhotoGeneration).mockClear();
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="photo" />);

    const file = new File([new Uint8Array([1, 2, 3])], "menu.png", { type: "image/png" });
    fireEvent.change(screen.getByLabelText("광고 사진 선택"), { target: { files: [file] } });
    fireEvent.change(screen.getByLabelText("사진 광고 요청 입력"), {
      target: { value: "이 사진으로 이미지만 광고 만들어줘" }
    });
    fireEvent.click(screen.getByText("이미지만 생성"));
    fireEvent.click(screen.getByRole("button", { name: /사진 기반 생성 시작/ }));

    await waitFor(() =>
      expect(api.startPhotoGeneration).toHaveBeenCalledWith({
        userInput: "이 사진으로 이미지만 광고 만들어줘",
        sourceImagePath: "data/uploads/photo_1.png",
        copyGenerationMode: "no_copy"
      })
    );
    await waitFor(() => expect(screen.getByText("AI가 브리프를 정리했어요")).toBeTruthy());
    expect(screen.getByText("문구 없이 이미지로만")).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "추천 문구" })).toBeNull();
  });

  it("routes photo generation directly to a backend brief in auto-pilot mode", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.uploadPhotoAsset).mockClear();
    vi.mocked(api.startPhotoGeneration).mockClear();
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="photo" />);

    const file = new File([new Uint8Array([1, 2, 3])], "menu.png", { type: "image/png" });
    fireEvent.change(screen.getByLabelText("광고 사진 선택"), { target: { files: [file] } });
    fireEvent.change(screen.getByLabelText("사진 광고 요청 입력"), {
      target: { value: "이 사진으로 딸기라떼 신메뉴 광고 만들어줘" }
    });
    fireEvent.click(screen.getByText("AI 자동 완성"));
    fireEvent.click(screen.getByRole("button", { name: /사진 기반 생성 시작/ }));

    await waitFor(() =>
      expect(api.startPhotoGeneration).toHaveBeenCalledWith({
        userInput: "이 사진으로 딸기라떼 신메뉴 광고 만들어줘",
        sourceImagePath: "data/uploads/photo_1.png",
        copyGenerationMode: "auto_pilot",
        userCustomHeadline: undefined,
        userCustomSubcopy: undefined
      })
    );
    await waitFor(() => expect(screen.getByText("AI가 브리프를 정리했어요")).toBeTruthy());
    expect(screen.getByText("AI가 고른 딸기라떼 한 잔")).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "추천 문구" })).toBeNull();
  });

  it("routes photo generation directly to a backend brief with user-provided copy", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.uploadPhotoAsset).mockClear();
    vi.mocked(api.startPhotoGeneration).mockClear();
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="photo" />);

    const file = new File([new Uint8Array([1, 2, 3])], "menu.png", { type: "image/png" });
    fireEvent.change(screen.getByLabelText("광고 사진 선택"), { target: { files: [file] } });
    fireEvent.change(screen.getByLabelText("사진 광고 요청 입력"), {
      target: { value: "이 사진으로 딸기라떼 신메뉴 광고 만들어줘" }
    });
    fireEvent.click(screen.getByText("직접 문구"));
    fireEvent.change(screen.getByLabelText("사진 직접 메인 문구 입력"), {
      target: { value: "오늘만 딸기라떼 반값" }
    });
    fireEvent.change(screen.getByLabelText("사진 직접 보조 문구 입력"), {
      target: { value: "오후 2시부터 5시까지" }
    });
    fireEvent.click(screen.getByRole("button", { name: /사진 기반 생성 시작/ }));

    await waitFor(() =>
      expect(api.startPhotoGeneration).toHaveBeenCalledWith({
        userInput: "이 사진으로 딸기라떼 신메뉴 광고 만들어줘",
        sourceImagePath: "data/uploads/photo_1.png",
        copyGenerationMode: "custom_input",
        userCustomHeadline: "오늘만 딸기라떼 반값",
        userCustomSubcopy: "오후 2시부터 5시까지"
      })
    );
    await waitFor(() => expect(screen.getByText("AI가 브리프를 정리했어요")).toBeTruthy());
    expect(screen.getByText("오늘만 딸기라떼 반값")).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "추천 문구" })).toBeNull();
  });

  it("sends saved brand kit context with photo generation requests", async () => {
    const api = await import("@/lib/api-client");
    vi.mocked(api.uploadPhotoAsset).mockClear();
    vi.mocked(api.startPhotoGeneration).mockClear();
    window.localStorage.setItem(
      BRAND_KIT_STORAGE_KEY,
      JSON.stringify({
        businessName: "연남 테스트 카페",
        businessType: "카페",
        region: "연남동",
        sns: "@test_cafe",
        tones: ["깔끔한"],
        colors: ["#FFD7C9"],
        phrases: ["예약은 DM 주세요"],
        products: ["대표 메뉴"],
        status: "saved",
        updatedAt: "2026-06-01T00:00:00.000Z"
      })
    );
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="photo" />);

    const file = new File([new Uint8Array([1, 2, 3])], "menu.png", { type: "image/png" });
    fireEvent.change(screen.getByLabelText("광고 사진 선택"), { target: { files: [file] } });
    fireEvent.change(screen.getByLabelText("사진 광고 요청 입력"), {
      target: { value: "이 사진으로 광고 만들어줘" }
    });
    fireEvent.click(screen.getByRole("button", { name: /사진 기반 생성 시작/ }));

    await waitFor(() => expect(api.startPhotoGeneration).toHaveBeenCalled());
    expect(vi.mocked(api.startPhotoGeneration).mock.calls[0][0]).toEqual(
      expect.objectContaining({
        sourceImagePath: "data/uploads/photo_1.png",
        userInput: expect.stringContaining("가게 이름: 연남 테스트 카페")
      })
    );
  });

  it("restores a pending photo turn after the chat route remounts", async () => {
    window.sessionStorage.setItem(
      "easyads_chat_turn_snapshot_v1",
      JSON.stringify({
        prompt: "이 사진으로 신메뉴 광고 만들어줘",
        response: {
          type: "copy_candidates",
          jobId: "photo_1",
          threadId: "photo_1_thread",
          status: "generating_copy_candidates",
          context: {
            businessType: "카페",
            itemOrService: "딸기라떼",
            promotionGoal: "신메뉴 출시"
          },
          copyCandidates: [{ id: "copy_photo_1", headline: "사진 속 메뉴를 오늘의 신메뉴로" }],
          recommendedCopyId: "copy_photo_1"
        }
      })
    );
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" />);

    await waitFor(() => expect(screen.getByText("AI가 이렇게 이해했어요")).toBeTruthy());
    expect(screen.getByText("딸기라떼")).toBeTruthy();
    expect(window.sessionStorage.getItem("easyads_chat_turn_snapshot_v1")).not.toBeNull();
  });

  it("keeps a completed photo brief after the chat start route remounts", async () => {
    window.sessionStorage.setItem(
      "easyads_chat_turn_snapshot_v1",
      JSON.stringify({
        prompt: "이 사진으로 신메뉴 광고 만들어줘",
        response: {
          type: "copy_candidates",
          jobId: "photo_1",
          threadId: "photo_1_thread",
          status: "generating_copy_candidates",
          context: {
            businessType: "카페",
            itemOrService: "딸기라떼",
            promotionGoal: "신메뉴 출시"
          },
          copyCandidates: [{ id: "copy_photo_1", headline: "사진 속 메뉴를 오늘의 신메뉴로" }],
          recommendedCopyId: "copy_photo_1"
        }
      })
    );
    window.sessionStorage.setItem(
      "easyads_chat_flow_snapshot_v1",
      JSON.stringify({
        prompt: "이 사진으로 신메뉴 광고 만들어줘",
        jobId: "photo_1",
        threadId: "photo_1_thread",
        context: {
          businessType: "카페",
          itemOrService: "딸기라떼",
          promotionGoal: "신메뉴 출시"
        },
        copyCandidates: [{ id: "copy_photo_1", headline: "사진 속 메뉴를 오늘의 신메뉴로" }],
        selectedCopyId: "copy_photo_1",
        selectedChannelId: "instagram-feed",
        selectedTone: "감성적인",
        customDirection: "",
        brief: {
          purpose: "신메뉴 출시",
          item: "딸기라떼",
          copy: "사진 속 메뉴를 오늘의 신메뉴로",
          tone: "감성적인 분위기",
          channel: "인스타 피드 (1:1)",
          imageDirection: "사진 속 상품이 잘 보이도록 깔끔한 배경과 문구 여백을 구성해요.",
          finalImagePath: null
        }
      })
    );
    (globalThis as typeof globalThis & { React: typeof React }).React = React;
    const { ChatGenerateClient } = await import("./ChatGenerateClient");

    render(<ChatGenerateClient initialSurface="chat" />);

    await waitFor(() => expect(screen.getByText("AI가 브리프를 정리했어요")).toBeTruthy());
    expect(screen.getByText("다음 단계에서 선택")).toBeTruthy();
    expect(screen.queryByText("사진 속 메뉴를 오늘의 신메뉴로")).toBeNull();
    expect(screen.queryByText("대화로 찰떡 이미지 만들기")).toBeNull();
    expect(window.sessionStorage.getItem("easyads_chat_turn_snapshot_v1")).toBeNull();
  });
});
