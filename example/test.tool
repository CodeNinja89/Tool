%% declarations
x: uint32;

oracle gcd(a: uint32, b: uint32, z: uint32) -> isGcd: bool {
    assumes a > 0 && b > 0 && z > 0;
    returns (((a % z == 0) && (b % z == 0)) ? isGcd == true : isGcd == false);
}

%% preconditions
%% postconditions
%% program