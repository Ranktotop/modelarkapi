import assert from "node:assert/strict";
import { test } from "node:test";

import {
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
