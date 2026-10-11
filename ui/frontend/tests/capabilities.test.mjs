import assert from "node:assert/strict";
import { test } from "node:test";

import {
  availableModes,
  nativeField,
  billingParty,
  providerLabel,
  continuationOf,
  hasParameter,
  parameterRange,
  promptRequired,
  resultVariants,
  rolesFor,
  extendsVideos,
  feature,
  groupModels,
  lockedValue,
  modeUnavailable,
  parameterValues,
  referenceLimit,
} from "../.test-build/capabilities.js";

const v1Only = {
  resolutions: ["480p", "720p"],
  ratios: ["adaptive", "16:9"],
  durations: [-1, 4, 5],
  defaults: { resolution: "720p", ratio: "adaptive", duration: 5 },
  reference_limits: { image: 9, video: 0, audio: 3 },
  reference_audio_requires_visual: true,
  output_formats: ["mp4"],
  task_types: [],
  supports_frames: false,
  supports_last_frame_role: false,
  adaptive_ratio_for_frames: false,
};

const seedance25 = {
  ...v1Only,
  reference_limits: { image: 30, video: 10, audio: 10 },
  schema_version: 2,
  provider: "modelark",
  parameters: {
    seconds: { values: ["auto", 4, 5, 30], default: 5 },
    resolution: { values: ["480p", "720p", "1080p"], default: "720p" },
    aspect_ratio: { values: ["adaptive", "16:9", "9:16"], default: "adaptive" },
    generate_audio: { default: true },
  },
  tasks: {
    text_to_video: {},
    image_to_video: { references: [{ role: "first_frame", types: ["image"], min: 1, max: 1 }] },
    reference_to_video: {
      references: [{ role: "reference", types: ["image", "video", "audio"], min: 1, max: 50 }],
      limits: [{ roles: ["reference"], types: ["image"], max: 30 }],
    },
    edit: {},
  },
  constraints: [
    { if: { task: ["image_to_video", "first_last_frame"] }, then: { aspect_ratio: ["adaptive"] }, message: "keeps ratio" },
    { if: { task: ["edit"] }, then: { aspect_ratio: ["adaptive"], seconds: ["auto"] }, message: "keeps input" },
  ],
  continuation: "last_frame",
  features: { real_human: true, last_frame_output: true, watermark: true },
};

const veo = {
  schema_version: 2,
  provider: "google",
  parameters: {
    seconds: { values: [4, 6, 8], default: 8 },
    resolution: { values: ["720p", "1080p"], default: "720p" },
    aspect_ratio: { values: ["16:9", "9:16"], default: "16:9" },
  },
  tasks: { text_to_video: {}, reference_to_video: { parameters: { seconds: { values: [8], default: 8 } } } },
  constraints: [],
  features: {},
};

test("v2 tasks decide which workflows are available", () => {
  assert.equal(modeUnavailable(seedance25, "edit"), null);
  assert.match(modeUnavailable(seedance25, "stitch") ?? "", /nicht/);
  assert.match(modeUnavailable(veo, "first_frame") ?? "", /nicht/);
});

test("v1-only documents keep the previous rules", () => {
  assert.match(modeUnavailable(v1Only, "first_last") ?? "", /Endframe/);
  assert.match(modeUnavailable(v1Only, "edit") ?? "", /Videoreferenzen/);
  assert.equal(modeUnavailable(v1Only, "multimodal"), null);
});

test("parameter values honour task overrides and fall back to v1", () => {
  assert.deepEqual(parameterValues(veo, "reference_to_video", "seconds"), [8]);
  assert.deepEqual(parameterValues(veo, "text_to_video", "seconds"), [4, 6, 8]);
  assert.deepEqual(parameterValues(seedance25, "text_to_video", "seconds"), [-1, 4, 5, 30]);
  assert.deepEqual(parameterValues(v1Only, "text_to_video", "seconds"), [-1, 4, 5]);
  assert.deepEqual(parameterValues(v1Only, "text_to_video", "aspect_ratio"), ["adaptive", "16:9"]);
});

test("task constraints lock values with their reason", () => {
  assert.deepEqual(lockedValue(seedance25, "image_to_video", "aspect_ratio"), { value: "adaptive", message: "keeps ratio" });
  assert.deepEqual(lockedValue(seedance25, "edit", "seconds"), { value: -1, message: "keeps input" });
  assert.equal(lockedValue(seedance25, "text_to_video", "aspect_ratio"), null);
});

test("reference limits come from task slots and group limits", () => {
  assert.equal(referenceLimit(seedance25, "reference_to_video", "image"), 30);
  assert.equal(referenceLimit(seedance25, "reference_to_video", "video"), 50);
  assert.equal(referenceLimit(veo, "text_to_video", "image"), 0);
  assert.equal(referenceLimit(v1Only, "reference_to_video", "audio"), 3);
});

test("features default sensibly for v1 documents", () => {
  assert.equal(feature(seedance25, "real_human"), true);
  assert.equal(feature(veo, "real_human"), false);
  assert.equal(feature(v1Only, "real_human"), true);
  assert.equal(feature(veo, "generate_audio"), false);
  assert.equal(feature(seedance25, "generate_audio"), true);
});

test("models are grouped by provider in a stable order", () => {
  const groups = groupModels([
    { id: "veo", label: "Veo", capabilities: veo },
    { id: "s25", label: "Seedance 2.5", capabilities: seedance25 },
    { id: "s20", label: "Seedance 2.0", capabilities: v1Only },
  ]);
  assert.deepEqual(groups.map(group => [group.label, group.models.map(model => model.id)]), [
    ["BytePlus ModelArk", ["s25", "s20"]],
    ["Google", ["veo"]],
  ]);
});

test("continuation follows the document and defaults to the last frame", () => {
  assert.equal(continuationOf(seedance25), "last_frame");
  assert.equal(continuationOf({ ...veo, continuation: "video_extension" }), "video_extension");
  assert.equal(continuationOf(v1Only), "last_frame");
  assert.equal(continuationOf(undefined), "none");
});

test("Veo extension and Omni multi-turn both continue by extending the video", () => {
  assert.equal(extendsVideos({ ...veo, continuation: "video_extension" }), true);
  assert.equal(extendsVideos({ ...veo, continuation: "multi_turn" }), true);
  assert.equal(extendsVideos(seedance25), false);
});

const klingTools = {
  schema_version: 2,
  provider: "kling",
  parameters: {
    seconds: { min: 3, max: 10, default: 5 },
    resolution: { values: ["720p", "1080p"], default: "720p" },
    speech: {},
  },
  tasks: {
    avatar: { references: [{ role: "subject", types: ["image"], min: 1, max: 1 }, { role: "speech", types: ["audio"], min: 0, max: 1 }], prompt_required: false },
    commerce_talking_agent: { references: [{ role: "avatar", types: ["image"], min: 0, max: 1 }, { role: "product", types: ["image"], min: 0, max: 5 }] },
  },
  prompt: { required: true },
  constraints: [],
  features: {},
};

test("roles for a reference come from the task's slots", () => {
  assert.deepEqual(rolesFor(klingTools, "commerce_talking_agent", "image"), ["avatar", "product"]);
  assert.deepEqual(rolesFor(klingTools, "avatar", "audio"), ["speech"]);
  assert.deepEqual(rolesFor(seedance25, "reference_to_video", "video"), ["reference"]);
  assert.deepEqual(rolesFor(v1Only, "reference_to_video", "image"), []);
});

test("prompt requirements follow the task, then the model", () => {
  assert.equal(promptRequired(klingTools, "avatar"), false);
  assert.equal(promptRequired(klingTools, "commerce_talking_agent"), true);
  assert.equal(promptRequired(v1Only, "text_to_video"), true);
});

test("ranges and parameter presence are exposed", () => {
  assert.deepEqual(parameterRange(klingTools, "avatar", "seconds"), { min: 3, max: 10 });
  assert.equal(parameterRange(klingTools, "avatar", "resolution"), null);
  assert.equal(hasParameter(klingTools, "avatar", "speech"), true);
  assert.equal(hasParameter(klingTools, "avatar", "negative_prompt"), false);
  assert.equal(hasParameter(v1Only, "text_to_video", "seconds"), true);
});

test("available modes list only the model's tasks", () => {
  const modes = [{ id: "text" }, { id: "avatar" }, { id: "edit" }];
  assert.deepEqual(availableModes(klingTools, modes).map(mode => mode.id), ["avatar"]);
  assert.deepEqual(availableModes(v1Only, modes).map(mode => mode.id), ["text", "avatar", "edit"]);
});

test("result variants are listed per output", () => {
  assert.deepEqual(resultVariants([{ index: 0, variants: ["video", "audio", "product_image_1"] }]), [
    { output: 0, variant: "video" },
    { output: 0, variant: "audio" },
    { output: 0, variant: "product_image_1" },
  ]);
  assert.deepEqual(resultVariants(undefined), [{ output: 0, variant: "video" }]);
});

test("provider labels and billing party follow the selected model", () => {
  assert.equal(providerLabel(undefined), "BytePlus ModelArk");
  assert.equal(providerLabel({ provider: "kling" }), "Kling");
  assert.equal(billingParty({ provider: "modelark" }), "BytePlus");
  assert.equal(billingParty({ provider: "google", backend: "vertex" }), "Google Cloud (Vertex AI)");
  assert.equal(billingParty({ provider: "google", backend: "gemini" }), "Google (Gemini API)");
  assert.equal(billingParty({ provider: "kling" }), "Kling");
});

test("native fields follow the model's list and stay open for v1 documents", () => {
  assert.equal(nativeField({ native_fields: ["priority"] }, "priority"), true);
  assert.equal(nativeField({ native_fields: ["camera_fixed"] }, "priority"), false);
  assert.equal(nativeField({ resolutions: ["720p"] }, "priority"), true);
  assert.equal(nativeField(undefined, "priority"), false);
});
