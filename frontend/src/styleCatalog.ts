import type { StyleId } from "./styleConfig";

interface StyleDetails {
  id: StyleId;
  name: string;
  description: string;
  colors: string[];
}

const details: Record<string, Omit<StyleDetails, "id">> = {
  "3d-technical-illustration": {
    name: "3D Technical Illustration",
    description: "Minh họa kỹ thuật chân thực, cắt lớp cấu tạo và diễn hoạt từng bộ phận theo lời đọc.",
    colors: ["#f3f6fa", "#175fc0", "#ed9c2c"],
  },
  "3d-motion-infographic": {
    name: "3D Motion Infographic",
    description: "Không gian 3D, camera chuyển động, ảnh tham chiếu và chú thích theo lời thuyết minh.",
    colors: ["#080f19", "#4eaae0", "#d94e73"],
  },
  "detailed-vector": {
    name: "Detailed vector",
    description: "Nhiều chi tiết, đổ bóng và texture. Phù hợp nội dung cần độ chính xác.",
    colors: ["#d7f0ef", "#2b9c9f", "#dc647b"],
  },
  "outlined-cartoon": {
    name: "Outlined cartoon",
    description: "Viền đậm, màu tươi, nhân vật biểu cảm. Dễ hiểu và thân thiện.",
    colors: ["#fff2d4", "#78ccc4", "#ffce64"],
  },
  flat: {
    name: "Flat",
    description: "Mảng màu phẳng, không viền. Tím lavender, vàng tươi và chi tiết trang trí nhẹ.",
    colors: ["#ffffff", "#9E91E1", "#FEC600"],
  },
  "flat-with-black": {
    name: "Flat with black",
    description: "Mảng màu phẳng kết hợp khối đen lớn, tạo điểm nhấn và độ tương phản rõ nét.",
    colors: ["#ffffff", "#171717", "#f26b4f"],
  },
  "halftone-line": {
    name: "Halftone line",
    description: "Nét vẽ đen và chấm halftone trên nền giấy ấm, gợi cảm giác tranh in.",
    colors: ["#f6f1e7", "#242424", "#99938b"],
  },
};

export function getStyle(id: StyleId): StyleDetails {
  const name = id.replaceAll("-", " ");
  return {
    id,
    ...(Object.hasOwn(details, id) ? details[id] : {
      name: name.charAt(0).toUpperCase() + name.slice(1),
      description: "Xem bản demo để khám phá phong cách minh họa này.",
      colors: details.flat.colors,
    }),
  };
}
