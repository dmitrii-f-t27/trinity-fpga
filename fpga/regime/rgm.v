`default_nettype none
// Три декодера поля режима из 16-битного слова -> (exponent, сдвиг мантиссы).
// Одинаковый интерфейс, одинаковая ширина, один харнесс: сравнимы построчно.

// --- 1. УНАРНЫЙ (класс posit): длина серии = |e|/2^es -------------------------
module rgm_unary #(parameter integer N=16, parameter integer ES=2)
  (input wire [N-1:0] w, output wire signed [8:0] e, output wire [4:0] sh);
  wire s = w[N-2];                       // направление серии
  reg [4:0] run; integer i; reg done;
  always @(*) begin
    run = 0; done = 0;
    for (i = N-2; i >= 0; i = i-1)
      if (!done) begin
        if (w[i] == s) run = run + 1'b1; else done = 1;
      end
  end
  wire [4:0] k = run;
  assign e  = s ? $signed({4'b0,k}) <<< ES : -($signed({4'b0,k}) <<< ES);
  assign sh = k + 5'd2;                  // знак + бит-терминатор
endmodule

// --- 2. ЛОГАРИФМИЧЕСКИЙ (класс takum): 3-битное поле длины + двоичный хвост ---
module rgm_log #(parameter integer N=16)
  (input wire [N-1:0] w, output wire signed [8:0] e, output wire [4:0] sh);
  wire [2:0] len = w[N-2:N-4];           // сколько бит несёт экспонента
  wire [7:0] pay = w[N-5:N-12];
  wire [7:0] msk = (8'hFF << (3'd7 - len)) & 8'hFF;
  assign e  = $signed({1'b0, pay & msk});
  assign sh = {2'b0, len} + 5'd4;
endmodule

// --- 3. КОРНЕВОЙ (промежуточный класс): длина серии k, |e| = k^2 --------------
module rgm_sqrt #(parameter integer N=16)
  (input wire [N-1:0] w, output wire signed [8:0] e, output wire [4:0] sh);
  wire s = w[N-2];
  reg [4:0] run; integer i; reg done;
  always @(*) begin
    run = 0; done = 0;
    for (i = N-2; i >= 0; i = i-1)
      if (!done) begin
        if (w[i] == s) run = run + 1'b1; else done = 1;
      end
  end
  wire [4:0] k = run;
  wire [9:0] sq = k * k;                 // <-- вот эта штука и есть цена класса
  assign e  = s ? $signed({1'b0,sq[8:0]}) : -$signed({1'b0,sq[8:0]});
  assign sh = k + 5'd2;
endmodule
